"""OddsFlow V3 — Fixture ingestion: manual add + upcoming feed."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

from app.db.database import get_conn
from app.engine.classify import classify_fixture
from app.frontend.jinja import templates
from app.settings import settings

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------

class FixtureAddPayload(BaseModel):
    date: str                        # "2026-06-01T15:00:00"
    home_team_id: int
    away_team_id: int
    league_id: int
    tier: int
    home_odd: float
    draw_odd: float
    away_odd: float
    btts_yes_odd: float | None = None
    btts_no_odd: float | None = None
    goals_over_25_odd: float | None = None
    corners_over_85_odd: float | None = None

    @field_validator("tier")
    @classmethod
    def tier_valid(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError("tier must be 1, 2, or 3")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_leagues(conn: Any) -> list[dict]:
    rows = conn.execute("SELECT id, name, country FROM leagues ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def _get_teams(conn: Any) -> list[dict]:
    rows = conn.execute("SELECT id, name FROM teams ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def _get_upcoming(conn: Any, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """
        SELECT f.*, l.name AS league_name,
               ht.name AS home_team_name, at2.name AS away_team_name
        FROM fixtures f
        LEFT JOIN leagues l   ON l.id  = f.league_id
        LEFT JOIN teams ht    ON ht.id = f.home_team_id
        LEFT JOIN teams at2   ON at2.id = f.away_team_id
        WHERE f.home_score IS NULL AND f.date >= date('now')
        ORDER BY f.date ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        clf = classify_fixture(d)
        d["draw_zone"] = clf["zone"]
        d["bts_pocket"] = clf["bts_pocket"]
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/ingest", response_class=HTMLResponse, tags=["ingest"])
async def ingest_page(request: Request) -> HTMLResponse:
    conn = get_conn(settings.sqlite_path)
    try:
        leagues = _get_leagues(conn)
        teams = _get_teams(conn)
        upcoming = _get_upcoming(conn)
    finally:
        conn.close()

    return templates.TemplateResponse("ingest.html", {
        "request": request,
        "leagues": leagues,
        "teams": teams,
        "upcoming": upcoming,
    })


@router.post("/api/fixtures/add", tags=["ingest"])
async def add_fixture(payload: FixtureAddPayload) -> dict:
    """Manually add an upcoming fixture."""
    conn = get_conn(settings.sqlite_path)
    try:
        for team_id in (payload.home_team_id, payload.away_team_id):
            if not conn.execute("SELECT 1 FROM teams WHERE id=?", (team_id,)).fetchone():
                raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
        if not conn.execute("SELECT 1 FROM leagues WHERE id=?", (payload.league_id,)).fetchone():
            raise HTTPException(status_code=404, detail=f"League {payload.league_id} not found")

        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """
            INSERT INTO fixtures (
                date, home_team_id, away_team_id, league_id, tier,
                home_odd, draw_odd, away_odd,
                btts_yes_odd, btts_no_odd,
                goals_over_25_odd, corners_over_85_odd,
                status, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'scheduled',?,?)
            """,
            (
                payload.date,
                payload.home_team_id, payload.away_team_id, payload.league_id, payload.tier,
                payload.home_odd, payload.draw_odd, payload.away_odd,
                payload.btts_yes_odd, payload.btts_no_odd,
                payload.goals_over_25_odd, payload.corners_over_85_odd,
                now, now,
            ),
        )
        fixture_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    clf = classify_fixture({
        "draw_odd": payload.draw_odd,
        "btts_yes_odd": payload.btts_yes_odd,
        "btts_no_odd": payload.btts_no_odd,
        "home_odd": payload.home_odd,
        "away_odd": payload.away_odd,
        "tier": payload.tier,
    })
    return {
        "fixture_id": fixture_id,
        "status": "scheduled",
        "draw_zone": clf["zone"],
        "df_level": clf.get("df"),
        "bts_pocket": clf["bts_pocket"],
    }


@router.get("/api/fixtures/upcoming", tags=["ingest"])
async def upcoming_fixtures_json(limit: int = 50) -> list[dict]:
    """Scheduled fixtures with live classification."""
    conn = get_conn(settings.sqlite_path)
    try:
        return _get_upcoming(conn, limit=limit)
    finally:
        conn.close()
