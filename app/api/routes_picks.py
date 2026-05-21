"""OddsFlow V3 — Picks: upcoming fixtures in promoted cells."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.db.database import get_conn
from app.engine.classify import classify_fixture
from app.engine.foundation import load_foundation
from app.engine.promotion import compute_foundation
from app.frontend.jinja import templates
from app.settings import settings

router = APIRouter()


def _picks_with_signals(conn, limit: int = 100) -> list[dict]:
    """Return upcoming fixtures that land in a promoted cell, enriched with cell signal."""
    rows = load_foundation(conn)
    data = compute_foundation(rows)

    # Build promoted cell lookup: (zone, bts_pocket) -> cell dict
    promoted = {
        (c["zone"], c["bts_pocket"]): c
        for c in data["all"]
        if c["cell_promoted"]
    }

    fixtures = conn.execute(
        """
        SELECT f.id, f.date, f.tier, f.draw_odd, f.btts_yes_odd, f.btts_no_odd,
               f.home_odd, f.away_odd,
               ht.name AS home_team_name, at2.name AS away_team_name,
               l.name  AS league_name
        FROM   fixtures f
        LEFT JOIN teams  ht  ON ht.id  = f.home_team_id
        LEFT JOIN teams  at2 ON at2.id = f.away_team_id
        LEFT JOIN leagues l  ON l.id   = f.league_id
        WHERE  f.status = 'scheduled'
        ORDER  BY f.date ASC
        LIMIT  ?
        """,
        (limit,),
    ).fetchall()

    picks = []
    for row in fixtures:
        d = dict(row)
        clf = classify_fixture(d)
        zone = clf["zone"]
        bts  = clf["bts_pocket"]
        if not zone or not bts:
            continue
        cell = promoted.get((zone, bts))
        if not cell:
            continue
        d["draw_zone"]   = zone
        d["bts_pocket"]  = bts
        d["cell"]        = cell
        picks.append(d)

    return picks


@router.get("/picks", response_class=HTMLResponse, tags=["picks"])
async def picks_page(request: Request) -> HTMLResponse:
    """Upcoming fixtures that classify into a currently promoted cell."""
    conn = get_conn(settings.sqlite_path)
    try:
        picks = _picks_with_signals(conn)
    finally:
        conn.close()

    return templates.TemplateResponse("picks.html", {
        "request": request,
        "picks": picks,
    })


@router.get("/api/picks", tags=["picks"])
async def picks_json(limit: int = 100) -> list[dict]:
    """JSON list of upcoming fixtures in promoted cells with cell signal data."""
    conn = get_conn(settings.sqlite_path)
    try:
        return _picks_with_signals(conn, limit=limit)
    finally:
        conn.close()
