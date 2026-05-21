"""OddsFlow V3 — Inspector: auto-surfaced findings from the Foundation Matrix."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db.database import get_conn
from app.engine.foundation import load_foundation
from app.engine.promotion import compute_foundation, PROMOTE_THRESHOLD, PROMOTE_LOWER
from app.frontend.jinja import templates
from app.settings import settings

router = APIRouter()


# ---------------------------------------------------------------------------
# Observation helpers
# ---------------------------------------------------------------------------

def _surface_findings(cells: list[dict[str, Any]], tier_label: str) -> list[dict[str, Any]]:
    """Auto-generate observations from cell data."""
    findings: list[dict[str, Any]] = []

    # Promoted cells
    for c in sorted(
        [x for x in cells if x["cell_promoted"]],
        key=lambda x: -max(x["gn_hit"], x["cn_hit"], x["threeway_hit"]),
    ):
        best_m, best_v = max(
            [("Goals", c["gn_hit"]), ("Corners", c["cn_hit"]), ("3-Way", c["threeway_hit"])],
            key=lambda x: x[1],
        )
        findings.append({
            "type": "fire",
            "zone": c["zone"],
            "bts": c["bts_pocket"],
            "headline": f"{c['zone'].replace('_', ' ').upper()} / {c['bts_pocket'].replace('_', ' ')}",
            "body": (
                f"{best_m} leads at {best_v:.1f}%  ·  "
                f"n={c['n_fixtures']} ({c['n_pct_of_zone']:.1f}% of zone)"
            ),
        })

    # Borderline — within 3pp of tolerance floor but not promoted
    for c in sorted(
        [
            x for x in cells
            if not x["cell_promoted"]
            and any(
                PROMOTE_LOWER - 3.0 <= v < PROMOTE_LOWER
                for v in (x["gn_hit"], x["cn_hit"], x["threeway_hit"])
            )
        ],
        key=lambda x: -max(x["gn_hit"], x["cn_hit"], x["threeway_hit"]),
    ):
        closest_m, closest_v = max(
            [("Goals", c["gn_hit"]), ("Corners", c["cn_hit"]), ("3-Way", c["threeway_hit"])],
            key=lambda x: x[1],
        )
        gap = round(PROMOTE_LOWER - closest_v, 1)
        findings.append({
            "type": "watch",
            "zone": c["zone"],
            "bts": c["bts_pocket"],
            "headline": f"{c['zone'].replace('_', ' ').upper()} / {c['bts_pocket'].replace('_', ' ')} — watch",
            "body": (
                f"{closest_m} at {closest_v:.1f}%  ·  "
                f"{gap}pp below tolerance floor  ·  n={c['n_fixtures']}"
            ),
        })

    # Measuring (low zone cells that would qualify)
    for c in [
        x for x in cells
        if x["zone"] == "low"
        and any(v >= PROMOTE_LOWER for v in (x["gn_hit"], x["cn_hit"], x["threeway_hit"]))
    ]:
        best_m, best_v = max(
            [("Goals", c["gn_hit"]), ("Corners", c["cn_hit"]), ("3-Way", c["threeway_hit"])],
            key=lambda x: x[1],
        )
        findings.append({
            "type": "meas",
            "zone": c["zone"],
            "bts": c["bts_pocket"],
            "headline": f"LOW / {c['bts_pocket'].replace('_', ' ')} — measuring",
            "body": (
                f"{best_m} at {best_v:.1f}% — meets tolerance but low zone suppressed  ·  n={c['n_fixtures']}"
            ),
        })

    return findings


def _zone_summary(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-zone aggregate for the overview strip."""
    acc: dict[str, dict] = defaultdict(lambda: {
        "n": 0, "cells": 0, "promoted": 0,
        "_g": 0.0, "_c": 0.0, "_t": 0.0,
    })
    for c in cells:
        z = acc[c["zone"]]
        z["n"] += c["n_fixtures"]
        z["cells"] += 1
        z["promoted"] += int(c["cell_promoted"])
        z["_g"] += c["gn_hit"]
        z["_c"] += c["cn_hit"]
        z["_t"] += c["threeway_hit"]

    result = []
    for name in ("strong", "standard", "low", "one_sided"):
        if name not in acc:
            continue
        z = acc[name]
        nc = z["cells"] or 1
        result.append({
            "zone": name,
            "n_fixtures": z["n"],
            "n_cells": z["cells"],
            "promoted": z["promoted"],
            "avg_goals": round(z["_g"] / nc, 1),
            "avg_corners": round(z["_c"] / nc, 1),
            "avg_3way": round(z["_t"] / nc, 1),
        })
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/inspector")


@router.get("/inspector", response_class=HTMLResponse, tags=["inspector"])
async def inspector_page(request: Request) -> HTMLResponse:
    conn = get_conn(settings.sqlite_path)
    try:
        rows = load_foundation(conn)
    finally:
        conn.close()

    data = compute_foundation(rows)

    return templates.TemplateResponse("inspector.html", {
        "request": request,
        "summary": data["summary"],
        "findings_all":   _surface_findings(data["all"],   "ALL"),
        "findings_t1":    _surface_findings(data["t1"],    "T1"),
        "findings_t2t3":  _surface_findings(data["t2t3"],  "T2+T3"),
        "zone_all":       _zone_summary(data["all"]),
        "zone_t1":        _zone_summary(data["t1"]),
        "zone_t2t3":      _zone_summary(data["t2t3"]),
        "total_cells":    len(data["all"]),
        "total_fixtures": data["summary"]["total_fixtures"],
        "promoted_count": data["summary"]["promoted_cells"],
    })


@router.get("/api/inspector", tags=["inspector"])
async def inspector_json() -> dict:
    conn = get_conn(settings.sqlite_path)
    try:
        rows = load_foundation(conn)
    finally:
        conn.close()

    data = compute_foundation(rows)
    return {
        "findings": _surface_findings(data["all"], "ALL"),
        "zone_summary": _zone_summary(data["all"]),
        "t1":   {"findings": _surface_findings(data["t1"],   "T1"),   "zones": _zone_summary(data["t1"])},
        "t2t3": {"findings": _surface_findings(data["t2t3"], "T2+T3"), "zones": _zone_summary(data["t2t3"])},
    }


@router.get("/api/inspector/cell", tags=["inspector"])
async def inspector_cell(zone: str, bts: str) -> dict:
    """Return foundation matrix data for a single zone × BTS cell.

    Used by the pre-match fixture card click — surfaces the cell's
    historical hit rates and promotion status for a given classification.
    """
    conn = get_conn(settings.sqlite_path)
    try:
        rows = load_foundation(conn)
    finally:
        conn.close()

    data = compute_foundation(rows)
    match = next(
        (c for c in data["all"] if c["zone"] == zone and c["bts_pocket"] == bts),
        None,
    )
    if not match:
        raise HTTPException(status_code=404, detail=f"Cell not found: {zone} / {bts}")
    return match


@router.get("/api/picks/calendar", tags=["inspector"])
async def picks_calendar(days: int = 28) -> dict:
    """28-day settled fixture performance calendar.

    Returns daily counts of goals over 2.5 and corners over 8.5 hits
    for all settled fixtures in the rolling window, for the inspector
    calendar overlay.
    """
    conn = get_conn(settings.sqlite_path)
    try:
        rows = conn.execute(
            """
            SELECT
                date(f.date) AS day,
                COUNT(*)     AS total,
                SUM(CASE WHEN (f.home_score + f.away_score) > 2.5  THEN 1 ELSE 0 END) AS goals_over,
                SUM(CASE WHEN COALESCE(fs.total_corners, 0) > 8.5  THEN 1 ELSE 0 END) AS corners_over,
                SUM(CASE WHEN f.home_score > f.away_score           THEN 1 ELSE 0 END) AS home_wins,
                SUM(CASE WHEN f.home_score = f.away_score           THEN 1 ELSE 0 END) AS draws,
                SUM(CASE WHEN f.home_score < f.away_score           THEN 1 ELSE 0 END) AS away_wins
            FROM fixtures f
            LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
            WHERE f.status = 'settled'
              AND f.home_score IS NOT NULL
              AND f.date >= date('now', '-' || ? || ' days')
            GROUP BY day
            ORDER BY day ASC
            """,
            (days,),
        ).fetchall()
        return {"days": [dict(r) for r in rows], "window": days}
    finally:
        conn.close()
