"""OddsFlow V4 — Analysis endpoints (/analysis/calibration_partition, /analysis/partition_stats_by_tier)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.db.database import get_conn
from app.engine.classify import zone_of, bts_of
from app.engine.static_policy import PROMOTED_CELLS
from app.settings import settings

router = APIRouter(prefix="/analysis", tags=["analysis"])


# ---------------------------------------------------------------------------
# Internal stats builder
# ---------------------------------------------------------------------------

def _build_partition_stats(
    conn: sqlite3.Connection,
    min_n: int = 30,
    tier_filter: int | str | None = None,
) -> list[dict[str, Any]]:
    """Compute per-(zone, bts) stats from settled fixtures."""
    clause = ""
    params: list[Any] = []
    if tier_filter is not None:
        if tier_filter == "untiered":
            clause = " AND (lg.tier IS NULL)"
        else:
            try:
                t = int(tier_filter)
                if t in (1, 2, 3):
                    clause = " AND lg.tier = ?"
                    params.append(t)
            except (ValueError, TypeError):
                pass

    rows = conn.execute(
        f"""
        SELECT f.draw_odd, f.btts_yes_odd, f.btts_no_odd,
               f.home_odd, f.away_odd,
               f.home_score, f.away_score,
               lg.tier AS league_tier
        FROM fixtures f
        LEFT JOIN leagues lg ON lg.id = f.league_id
        WHERE f.home_score IS NOT NULL
          AND f.draw_odd IS NOT NULL
          AND f.btts_yes_odd IS NOT NULL
          AND f.btts_no_odd IS NOT NULL
          AND f.home_odd IS NOT NULL
          AND f.away_odd IS NOT NULL
          {clause}
        """,
        params,
    ).fetchall()

    # Accumulate per cell
    acc: dict[tuple[str, str], dict] = {}
    for r in rows:
        zone = zone_of(r["draw_odd"])
        bts = bts_of(r["btts_yes_odd"], r["btts_no_odd"])
        if zone is None or bts is None:
            continue

        key = (zone, bts)
        if key not in acc:
            acc[key] = {
                "zone": zone, "bts": bts,
                "n": 0, "tw_hits": 0.0,
                "odd_sum": 0.0, "odd_n": 0,
            }
        c = acc[key]
        c["n"] += 1

        # Threeway outcome
        home_s, away_s = r["home_score"], r["away_score"]
        home_o, away_o = r["home_odd"], r["away_odd"]
        alpha_home = (home_o or 999) <= (away_o or 999)
        alpha_wins = (home_s > away_s) if alpha_home else (away_s > home_s)
        draw = (home_s == away_s)

        if zone in ("strong", "standard"):
            hit = 1.0 if (alpha_wins or draw) else 0.0
            fav_odd = min(home_o, away_o) if home_o and away_o else None
        else:
            hit = 1.0 if alpha_wins else 0.0
            fav_odd = min(home_o, away_o) if home_o and away_o else None

        c["tw_hits"] += hit
        if fav_odd:
            c["odd_sum"] += fav_odd
            c["odd_n"] += 1

    result: list[dict[str, Any]] = []
    for (zone, bts), c in acc.items():
        n = c["n"]
        if n < min_n:
            continue
        hit_rate = c["tw_hits"] / n
        avg_odd = round(c["odd_sum"] / c["odd_n"], 3) if c["odd_n"] > 0 else None
        edge = round(hit_rate - (1.0 / avg_odd), 4) if avg_odd and avg_odd > 0 else None
        cell = PROMOTED_CELLS.get((zone, bts))
        is_promoted = bool(cell and cell.get("cell_promoted"))
        pick_label = cell["threeway_pick"] if cell else ("DNB" if zone in ("strong", "standard") else "Alpha Win")

        result.append({
            "zone_group":            zone,
            "bts_v2":                bts,
            "df_label":              "—",
            "n":                     n,
            "hit_rate":              round(hit_rate, 4),
            "avg_odd":               avg_odd,
            "edge":                  edge,
            "dominant_direction":    pick_label,
            "dir_concentration_pct": round(hit_rate * 100, 1),
            "predictability_hint":   "positive" if is_promoted else ("mixed" if hit_rate >= 0.5 else "negative"),
            "is_promoted":           is_promoted,
            "is_discarded":          False,
            "is_emerging_watch":     False,
            "is_emerging_fire":      False,
            "is_emerging_discard":   False,
            "passes_wilson":         False,
            "passes_hw":             False,
        })

    result.sort(key=lambda r: -r["n"])
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/calibration_partition")
def calibration_partition(
    min_n: int = Query(30, ge=1, le=10000),
    strategy: str | None = Query(None),
) -> dict[str, Any]:
    """Per-(zone, bts) hit rates from all settled fixtures. Stone PROMOTE from static_policy."""
    conn = get_conn(settings.sqlite_path)
    try:
        rows = _build_partition_stats(conn, min_n=min_n)
    finally:
        conn.close()

    return {
        "count":                   len(rows),
        "min_n":                   min_n,
        "strategy_filter":         strategy,
        "promote_total":           sum(1 for r in rows if r["is_promoted"]),
        "discard_total":           0,
        "emerging_watch_total":    0,
        "emerging_fire_total":     0,
        "emerging_discard_total":  0,
        "partitions":              rows,
    }


@router.get("/partition_stats_by_tier")
def partition_stats_by_tier(
    min_n: int = Query(1, ge=1, le=10000),
    strategy: str | None = Query(None),
) -> dict[str, Any]:
    """Same per-cell stats stratified by league tier (for tier-specific Analysis view)."""
    conn = get_conn(settings.sqlite_path)
    try:
        tiers: list[int | str | None] = [1, 2, 3, "untiered"]
        all_rows: list[dict[str, Any]] = []
        for t in tiers:
            tier_rows = _build_partition_stats(conn, min_n=min_n, tier_filter=t)
            tier_key = f"T{t}" if t in (1, 2, 3) else "untiered"
            for r in tier_rows:
                all_rows.append({
                    "tier":     t if t != "untiered" else None,
                    "tier_key": tier_key,
                    "zone":     r["zone_group"],
                    "bts_v2":   r["bts_v2"],
                    **{k: r[k] for k in ("n", "hit_rate", "avg_odd", "edge",
                                         "dominant_direction", "dir_concentration_pct",
                                         "predictability_hint", "is_promoted")},
                })
    finally:
        conn.close()

    return {
        "count":           len(all_rows),
        "min_n":           min_n,
        "strategy_filter": strategy,
        "by_tier": {
            "T1":       sum(1 for r in all_rows if r["tier"] == 1),
            "T2":       sum(1 for r in all_rows if r["tier"] == 2),
            "T3":       sum(1 for r in all_rows if r["tier"] == 3),
            "untiered": sum(1 for r in all_rows if r["tier"] is None),
        },
        "partitions": all_rows,
    }
