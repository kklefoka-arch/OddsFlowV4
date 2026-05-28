"""OddsFlow V3 — Fixture management routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.db.database import get_conn
from app.engine.classify import classify_fixture
from app.frontend.jinja import templates
from app.settings import settings

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SettlePayload(BaseModel):
    home_score: int
    away_score: int
    home_corners: int | None = None
    away_corners: int | None = None
    home_tackles: int | None = None
    away_tackles: int | None = None
    fouls_h: int | None = None
    fouls_a: int | None = None
    yellow_cards_h: int | None = None
    yellow_cards_a: int | None = None
    xg_h: float | None = None
    xg_a: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: Any) -> dict:
    """Convert a sqlite3.Row (or mapping) to a plain dict."""
    return dict(row)


def _upcoming_fixtures(conn: Any) -> list[dict]:
    """Query scheduled fixtures with their classification fields."""
    cursor = conn.execute(
        """
        SELECT f.*, l.name AS league_name, l.country
        FROM fixtures f
        LEFT JOIN leagues l ON l.id = f.league_id
        WHERE f.home_score IS NULL
          AND f.date >= date('now')
          AND f.date <= date('now', '+30 days')
        ORDER BY f.date ASC
        """
    )
    rows = cursor.fetchall()
    result = []
    for row in rows:
        d = _row_to_dict(row)
        # Enrich with live classification (in case columns are stale)
        clf = classify_fixture(d)
        d["draw_zone"] = clf["zone"]
        d["bts_pocket"] = clf["bts_pocket"]
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/fixtures", response_class=HTMLResponse, tags=["fixtures"])
async def fixtures_page(request: Request) -> HTMLResponse:
    """Render the upcoming fixtures HTML page.

    Args:
        request: FastAPI request (required by Jinja2).

    Returns:
        Rendered fixtures.html with upcoming fixture list.
    """
    conn = get_conn(settings.sqlite_path)
    try:
        fixtures = _upcoming_fixtures(conn)
    finally:
        conn.close()

    return templates.TemplateResponse(
        "fixtures.html",
        {"request": request, "fixtures": fixtures},
    )


@router.get("/api/fixtures", tags=["fixtures"])
async def fixtures_json() -> list[dict]:
    """Return upcoming (scheduled) fixtures as JSON with classification.

    Returns:
        List of fixture dicts including draw_zone and bts_pocket.
    """
    conn = get_conn(settings.sqlite_path)
    try:
        fixtures = _upcoming_fixtures(conn)
    finally:
        conn.close()

    return fixtures


@router.post("/api/fixtures/settle/{fixture_id}", tags=["fixtures"])
async def settle_fixture(fixture_id: int, payload: SettlePayload) -> dict:
    """Mark a fixture as settled and record its result.

    Updates the fixture row with scores, sets status='settled',
    and upserts fixture_stats with any provided corner/stat data.

    Args:
        fixture_id: Primary key of the fixture to settle.
        payload:    Result data (scores, corners, optional stats).

    Returns:
        Confirmation dict with fixture_id and updated status.

    Raises:
        HTTPException 404: If fixture_id does not exist.
        HTTPException 409: If fixture is already settled.
    """
    conn = get_conn(settings.sqlite_path)
    try:
        row = conn.execute(
            "SELECT id, status FROM fixtures WHERE id = ?", (fixture_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Fixture not found")
        if dict(row).get("home_score") is not None:
            raise HTTPException(status_code=409, detail="Fixture already settled")

        total_goals = payload.home_score + payload.away_score
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """
            UPDATE fixtures
            SET home_score  = ?,
                away_score  = ?,
                total_goals = ?,
                status      = 'settled',
                updated_at  = ?
            WHERE id = ?
            """,
            (payload.home_score, payload.away_score, total_goals, now, fixture_id),
        )

        # Upsert fixture_stats if any stat provided
        total_corners: int | None = None
        if payload.home_corners is not None and payload.away_corners is not None:
            total_corners = payload.home_corners + payload.away_corners

        conn.execute(
            """
            INSERT INTO fixture_stats (
                fixture_id, home_corners, away_corners, total_corners,
                home_tackles, away_tackles, fouls_h, fouls_a,
                yellow_cards_h, yellow_cards_a, xg_h, xg_a
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fixture_id) DO UPDATE SET
                home_corners   = excluded.home_corners,
                away_corners   = excluded.away_corners,
                total_corners  = excluded.total_corners,
                home_tackles   = excluded.home_tackles,
                away_tackles   = excluded.away_tackles,
                fouls_h        = excluded.fouls_h,
                fouls_a        = excluded.fouls_a,
                yellow_cards_h = excluded.yellow_cards_h,
                yellow_cards_a = excluded.yellow_cards_a,
                xg_h           = excluded.xg_h,
                xg_a           = excluded.xg_a
            """,
            (
                fixture_id,
                payload.home_corners, payload.away_corners, total_corners,
                payload.home_tackles, payload.away_tackles,
                payload.fouls_h, payload.fouls_a,
                payload.yellow_cards_h, payload.yellow_cards_a,
                payload.xg_h, payload.xg_a,
            ),
        )

        # Write pick_results for any emit_log rows on this fixture
        emit_rows = conn.execute(
            "SELECT pick_uuid, market, pick FROM emit_log WHERE fixture_id = ?",
            (fixture_id,),
        ).fetchall()
        if emit_rows:
            from app.api.routes_picks import settle_pick
            # Re-read the odds we just set
            odds_row = conn.execute(
                "SELECT home_odd, away_odd FROM fixtures WHERE id = ?", (fixture_id,)
            ).fetchone()
            home_o = dict(odds_row).get("home_odd") if odds_row else None
            away_o = dict(odds_row).get("away_odd") if odds_row else None
            # V3.1 (2026-05-28): pass pick + total_corners (from payload if
            # operator supplied it, else from fixture_stats which we just upserted).
            corners_total = total_corners
            if corners_total is None:
                fs_row = conn.execute(
                    "SELECT total_corners FROM fixture_stats WHERE fixture_id = ?",
                    (fixture_id,),
                ).fetchone()
                corners_total = fs_row["total_corners"] if fs_row else None
            for er in emit_rows:
                outcome_val = settle_pick(
                    er["market"],
                    payload.home_score, payload.away_score,
                    home_o, away_o,
                    er["pick"] or "", total_corners=corners_total,
                )
                if outcome_val is None:
                    continue
                outcome_label = ("WIN" if outcome_val == 1.0 else
                                 "VOID" if outcome_val == 0.5 else "LOSS")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO pick_results
                      (pick_uuid, settled_at, outcome, actual_value)
                    VALUES (?, ?, ?, ?)
                    """,
                    (er["pick_uuid"], now, outcome_label, outcome_val),
                )

        conn.commit()

    finally:
        conn.close()

    return {"fixture_id": fixture_id, "status": "settled", "total_goals": total_goals}
