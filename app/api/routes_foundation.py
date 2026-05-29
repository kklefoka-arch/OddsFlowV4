"""OddsFlow V4 — Foundation Matrix routes.

Hit rates per (zone × BTS pocket) cell — V3 partition shape (Session 19 restored).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.db.database import get_conn
from app.engine.foundation import load_foundation
from app.engine.promotion import compute_foundation
from app.frontend.jinja import templates
from app.settings import settings

router = APIRouter()


@router.get("/foundation", response_class=HTMLResponse, tags=["foundation"])
async def foundation_page(request: Request) -> HTMLResponse:
    """Render the Foundation Matrix HTML page.

    Args:
        request: FastAPI request (required by Jinja2).

    Returns:
        Rendered foundation.html with foundation matrix data.
    """
    conn = get_conn(settings.sqlite_path)
    try:
        rows = load_foundation(conn)
    finally:
        conn.close()

    data = compute_foundation(rows)
    return templates.TemplateResponse(
        "foundation.html",
        {"request": request, "foundation": data},
    )


@router.get("/api/foundation", tags=["foundation"])
async def foundation_json() -> dict:
    """Return the full Foundation Matrix as JSON.

    Each cell carries an explicit ``partition_key`` field (``"<zone>:<bts>"``)
    so downstream tools can key off the same string the rest of the API uses
    (inspector drift, reports, picks).

    ``cell_promoted`` is overlaid from ``V3_ACTIVE`` — the live pick policy —
    rather than the foundation algorithm's per-cell threshold. The foundation
    algorithm's per-market ``goals_promote`` / ``corners_promote`` /
    ``threeway_promote`` strings are preserved alongside (they reflect the
    foundation matrix's own per-market evaluation under PROMOTE_THRESHOLD).
    This way the Analysis tab shows what is actually firing live; the
    per-market columns still show the historical-threshold story.

    Returns:
        Dict with keys ``all``, ``t1``, ``t2t3``, and ``summary``.
    """
    from app.engine.static_policy import V3_ACTIVE  # local import — avoid circular
    conn = get_conn(settings.sqlite_path)
    try:
        rows = load_foundation(conn)
    finally:
        conn.close()

    data = compute_foundation(rows)  # cells now carry df (3-key partition)
    live_keys = set(V3_ACTIVE.keys())
    promoted_count = 0
    for section in ("all", "t1", "t2t3"):
        for cell in data.get(section, []) or []:
            zone = cell["zone"]
            bts = cell["bts_pocket"]
            df = cell.get("df", "")
            key = (zone, df, bts)
            cell["partition_key"] = f"{zone}:{df}:{bts}" if df else f"{zone}:{bts}"
            cell["cell_promoted"] = key in live_keys
            if section == "all" and cell["cell_promoted"]:
                promoted_count += 1
    if isinstance(data.get("summary"), dict):
        data["summary"]["promoted_cells"] = promoted_count
    return data
