"""OddsFlow V4 — Upcoming fixtures endpoint for the SPA Upcoming tab."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.db.database import get_conn
from app.engine.classify import classify_fixture
from app.engine.foundation import load_foundation
from app.engine.promotion import compute_foundation, PROMOTE, PROMOTE_TOLERANCE
from app.settings import settings

router = APIRouter(tags=["upcoming"])


@router.get("/upcoming")
def upcoming(
    days: int = Query(7, ge=1, le=14),
    tier: str | None = Query(None),
) -> dict[str, Any]:
    """All upcoming fixtures in the window with zone/BTS classification.

    Returns every fixture regardless of promotion status so the operator
    can see what the engine sees before the partition filter applies.
    """
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    horizon = (datetime.now(tz=timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")

    tier_clause = ""
    tier_params: list[Any] = []
    if tier:
        if tier == "untiered":
            tier_clause = " AND (lg.tier IS NULL)"
        else:
            try:
                t = int(tier)
                if t in (1, 2, 3):
                    tier_clause = " AND lg.tier = ?"
                    tier_params.append(t)
            except ValueError:
                pass

    # V3 stone policy directly (the authoritative promotion set), not a
    # re-derivation from live data. Fixes M4 (Session 15 process audit).
    from app.engine.static_policy import V3_ACTIVE
    promoted_keys: set[tuple[str, str]] = set(V3_ACTIVE.keys())

    conn = get_conn(settings.sqlite_path)
    try:

        rows = conn.execute(
            f"""
            SELECT f.id, f.date, f.tier,
                   f.home_odd, f.draw_odd, f.away_odd,
                   f.btts_yes_odd, f.btts_no_odd,
                   f.goals_over_15_odd, f.corners_over_85_odd,
                   ht.name AS home_team_name, at2.name AS away_team_name,
                   lg.name AS league_name, lg.country, lg.tier AS league_tier
            FROM fixtures f
            LEFT JOIN teams ht  ON ht.id  = f.home_team_id
            LEFT JOIN teams at2 ON at2.id = f.away_team_id
            LEFT JOIN leagues lg ON lg.id = f.league_id
            WHERE f.home_score IS NULL
              AND f.date >= ?
              AND substr(f.date, 1, 10) <= ?
              {tier_clause}
            ORDER BY f.date ASC
            """,
            [today, horizon, *tier_params],
        ).fetchall()
    finally:
        conn.close()

    data = []
    by_tier: dict[str, int] = {}
    promoted_count = 0

    for row in rows:
        d = dict(row)
        clf = classify_fixture(d)
        zone = clf.get("zone")
        bts = clf.get("bts_pocket")
        partition_promoted = bool(zone and bts and (zone, bts) in promoted_keys)

        tier_key = str(d.get("league_tier") or d.get("tier") or "")
        if tier_key:
            by_tier[tier_key] = by_tier.get(tier_key, 0) + 1

        if partition_promoted:
            promoted_count += 1

        data.append({
            "id":              d["id"],
            "kickoff_utc":     d["date"],
            "home_team_name":  d["home_team_name"] or "",
            "away_team_name":  d["away_team_name"] or "",
            "league_name":     d["league_name"] or "",
            "country":         d.get("country") or "",
            "tier":            d.get("league_tier") or d.get("tier"),
            "home_odd":        d.get("home_odd"),
            "draw_odd":        d.get("draw_odd"),
            "away_odd":        d.get("away_odd"),
            "btts_yes_odd":    d.get("btts_yes_odd"),
            "btts_no_odd":     d.get("btts_no_odd"),
            "zone_group":      zone or "—",
            "bts_v2":          bts or "—",
            "partition_promoted": partition_promoted,
        })

    return {
        "count": len(data),
        "window_days": days,
        "summary": {
            "by_tier": by_tier,
            "partition_promoted": promoted_count,
        },
        "data": data,
    }
