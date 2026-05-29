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

    Returns:
        Dict with keys ``all``, ``t1``, ``t2t3``, and ``summary``.
    """
    conn = get_conn(settings.sqlite_path)
    try:
        rows = load_foundation(conn)
    finally:
        conn.close()

    data = compute_foundation(rows)
    for section in ("all", "t1", "t2t3"):
        for cell in data.get(section, []) or []:
            cell["partition_key"] = f"{cell['zone']}:{cell['bts_pocket']}"
    return data
