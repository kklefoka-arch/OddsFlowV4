"""OddsFlow V3 — Inspector: auto-surfaced findings from the Foundation Matrix."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

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
