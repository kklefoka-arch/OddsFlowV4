"""OddsFlow V4 — Reports endpoints (emit_performance, emit_recent, settle_activity, paper_trading.csv)."""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.routes_picks import settle_pick
from app.db.database import get_conn
from app.engine.classify import zone_of, bts_of
from app.engine.foundation import load_foundation
from app.engine.promotion import compute_foundation, PROMOTE, PROMOTE_TOLERANCE
from app.settings import settings

router = APIRouter(prefix="/reports", tags=["reports"])


def _tier_where_clause(tier: str | None) -> tuple[str, list]:
    if not tier:
        return "", []
    if tier == "untiered":
        return " AND (lg.tier IS NULL)", []
    try:
        t = int(tier)
        if t in (1, 2, 3):
            return " AND lg.tier = ?", [t]
    except ValueError:
        pass
    return "", []


# ---------------------------------------------------------------------------
# GET /reports/emit_performance
# ---------------------------------------------------------------------------

@router.get("/emit_performance")
def emit_performance(
    tier: str | None = Query(None),
) -> dict[str, Any]:
    """Multi-window engine-emit performance, on-the-fly settled from fixture scores."""
    now = datetime.now(tz=timezone.utc)
    cutoff_180 = now - timedelta(days=180)
    tier_clause, tier_params = _tier_where_clause(tier)

    conn = get_conn(settings.sqlite_path)
    try:
        rows = conn.execute(
            f"""
            SELECT em.emitted_at, em.fixture_id, em.market, em.pick,
                   f.home_score, f.away_score, f.home_odd, f.away_odd
            FROM emit_log em
            JOIN fixtures f ON f.id = em.fixture_id
            LEFT JOIN leagues lg ON lg.id = f.league_id
            WHERE em.emitted_at >= ?{tier_clause}
            """,
            [cutoff_180.strftime("%Y-%m-%d %H:%M:%S"), *tier_params],
        ).fetchall()
    finally:
        conn.close()

    legs: list[tuple[datetime, int, str, str, float | None]] = []
    for r in rows:
        try:
            emitted_at = datetime.fromisoformat((r["emitted_at"] or "").replace(" ", "T"))
            if emitted_at.tzinfo is None:
                emitted_at = emitted_at.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        outcome = settle_pick(r["market"], r["home_score"], r["away_score"],
                               r["home_odd"], r["away_odd"], r["pick"])
        legs.append((emitted_at, r["fixture_id"], r["market"], r["pick"], outcome))

    windows_out = []
    for days in (1, 3, 7, 30, 90, 180):
        cutoff = now - timedelta(days=days)
        in_window = [l for l in legs if l[0] >= cutoff]
        settled = [l for l in in_window if l[4] is not None]
        unsettled = [l for l in in_window if l[4] is None]
        wins = sum(1 for l in settled if l[4] == 1.0)
        voids = sum(1 for l in settled if l[4] == 0.5)
        losses = sum(1 for l in settled if l[4] == 0.0)
        n_settled = len(settled)
        hit_score = wins + 0.5 * voids
        hit_rate_legs = (hit_score / n_settled) if n_settled > 0 else None

        events: dict[tuple[int, str], list[float]] = {}
        for (_, fid, mkt, _pick, outcome) in ((l[0], l[1], l[2], l[3], l[4]) for l in in_window):
            if outcome is None:
                continue
            events.setdefault((fid, mkt), []).append(outcome)
        events_settled = len(events)
        wins_ev = sum(1 for outs in events.values() if any(o == 1.0 for o in outs))
        voids_ev = sum(1 for outs in events.values()
                       if all(o != 1.0 for o in outs) and any(o == 0.5 for o in outs))
        losses_ev = events_settled - wins_ev - voids_ev
        hit_ev = (wins_ev + 0.5 * voids_ev) / events_settled if events_settled > 0 else None

        windows_out.append({
            "name":     f"{days}d",
            "days":     days,
            "fixtures": len({l[1] for l in in_window}),
            "legs": {
                "total":     len(in_window),
                "settled":   n_settled,
                "unsettled": len(unsettled),
                "wins":      wins,
                "voids":     voids,
                "losses":    losses,
                "hit_rate":  round(hit_rate_legs * 100, 1) if hit_rate_legs is not None else None,
            },
            "events": {
                "settled":  events_settled,
                "wins":     wins_ev,
                "voids":    voids_ev,
                "losses":   losses_ev,
                "hit_rate": round(hit_ev * 100, 1) if hit_ev is not None else None,
            },
        })

    return {
        "as_of":   now.isoformat(),
        "tier":    tier,
        "windows": windows_out,
        "note": (
            "legs.* counts every emit_log row separately. "
            "events.* collapses per (fixture, market) into one event."
        ),
    }


# ---------------------------------------------------------------------------
# GET /reports/emit_recent
# ---------------------------------------------------------------------------

@router.get("/emit_recent")
def emit_recent(
    days: int = Query(7, ge=1, le=90),
    tier: str | None = Query(None),
) -> dict[str, Any]:
    """Per-fixture readback of recent emits with on-the-fly outcomes."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    tier_clause, tier_params = _tier_where_clause(tier)

    conn = get_conn(settings.sqlite_path)
    try:
        rows = conn.execute(
            f"""
            SELECT em.pick_uuid, em.emitted_at, em.fixture_id, em.market, em.pick,
                   em.pick_odd,
                   em.zone AS em_zone, em.df_level AS em_df, em.bts_pocket AS em_bts,
                   f.date AS kickoff_utc,
                   f.home_score, f.away_score, f.home_odd, f.away_odd,
                   f.btts_yes_odd, f.btts_no_odd,
                   lg.name AS league_name, lg.country, lg.tier,
                   th.name AS home_team, ta.name AS away_team
            FROM emit_log em
            JOIN fixtures f ON f.id = em.fixture_id
            LEFT JOIN leagues lg ON lg.id = f.league_id
            LEFT JOIN teams th ON th.id = f.home_team_id
            LEFT JOIN teams ta ON ta.id = f.away_team_id
            WHERE em.emitted_at >= ?{tier_clause}
            ORDER BY f.date DESC, em.emitted_at DESC
            """,
            [cutoff.strftime("%Y-%m-%d %H:%M:%S"), *tier_params],
        ).fetchall()
    finally:
        conn.close()

    # -- also fetch corners from fixture_stats for deferred_corners display --
    # (simplified: we don't have corners in emit_log for V4)

    by_fixture: dict[int, dict[str, Any]] = {}
    for r in rows:
        fx_id = r["fixture_id"]
        # V3.1: build partition_key from emit_log columns (the cell as fired)
        em_zone = r["em_zone"]; em_df = r["em_df"]; em_bts = r["em_bts"]
        pk = None
        if em_zone and em_bts:
            pk = f"{em_zone}:{em_df}:{em_bts}" if em_df else f"{em_zone}:{em_bts}"
        fx = by_fixture.setdefault(fx_id, {
            "fixture_id":   fx_id,
            "kickoff_utc":  r["kickoff_utc"],
            "league":       r["league_name"],
            "country":      r["country"],
            "tier":         r["tier"],
            "home_team":    r["home_team"],
            "away_team":    r["away_team"],
            "home_score":   r["home_score"],
            "away_score":   r["away_score"],
            "home_corners": None,
            "away_corners": None,
            "partition_key": pk,
            "legs": [],
            "totals": {"wins": 0, "voids": 0, "losses": 0, "pending": 0},
        })
        outcome = settle_pick(r["market"], r["home_score"], r["away_score"],
                               r["home_odd"], r["away_odd"], r["pick"])
        lbl = ("PENDING" if outcome is None else
               "WIN" if outcome == 1.0 else
               "VOID" if outcome == 0.5 else "LOSS")
        fx["legs"].append({
            "pick_uuid":     r["pick_uuid"],
            "emitted_at":    r["emitted_at"],
            "market":        r["market"],
            "pick":          r["pick"],
            "pick_odd":      r["pick_odd"],
            "outcome":       outcome,
            "outcome_label": lbl,
        })
        if lbl == "WIN":     fx["totals"]["wins"]    += 1
        elif lbl == "VOID":  fx["totals"]["voids"]   += 1
        elif lbl == "LOSS":  fx["totals"]["losses"]  += 1
        else:                fx["totals"]["pending"] += 1

    fixtures = sorted(by_fixture.values(),
                      key=lambda fx: fx["kickoff_utc"] or "", reverse=True)
    now = datetime.now(tz=timezone.utc)
    return {
        "as_of":          now.isoformat(),
        "window_days":    days,
        "tier":           tier,
        "fixtures_count": len(fixtures),
        "legs_count":     sum(len(fx["legs"]) for fx in fixtures),
        "totals": {
            "wins":    sum(fx["totals"]["wins"]    for fx in fixtures),
            "voids":   sum(fx["totals"]["voids"]   for fx in fixtures),
            "losses":  sum(fx["totals"]["losses"]  for fx in fixtures),
            "pending": sum(fx["totals"]["pending"] for fx in fixtures),
        },
        "fixtures": fixtures,
    }


# ---------------------------------------------------------------------------
# GET /reports/settle_activity
# ---------------------------------------------------------------------------

@router.get("/settle_activity")
def settle_activity(
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    """Post-match settlement activity. Uses pick_results table + system_health."""
    now = datetime.now(tz=timezone.utc)
    cutoff_sql = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn(settings.sqlite_path)
    try:
        # Per-day settlements from pick_results
        by_day = conn.execute(
            """SELECT date(settled_at) AS d, COUNT(*) AS settled_count
               FROM pick_results
               WHERE settled_at >= ?
               GROUP BY date(settled_at)
               ORDER BY d DESC""",
            (cutoff_sql,),
        ).fetchall()

        # System health — last cron heartbeat
        last_clean = None
        last_heartbeat = None
        try:
            lc = conn.execute(
                """SELECT recorded_at, value FROM system_health
                   WHERE metric='cron_heartbeat' AND value LIKE '%step=complete%'
                   ORDER BY recorded_at DESC LIMIT 1"""
            ).fetchone()
            if lc:
                last_clean = {"recorded_at": lc["recorded_at"], "value": lc["value"]}
        except Exception:
            pass
        try:
            lh = conn.execute(
                """SELECT recorded_at, value FROM system_health
                   WHERE metric='cron_heartbeat'
                   ORDER BY recorded_at DESC LIMIT 1"""
            ).fetchone()
            if lh:
                last_heartbeat = {"recorded_at": lh["recorded_at"], "value": lh["value"]}
        except Exception:
            pass

    finally:
        conn.close()

    return {
        "as_of":            now.isoformat(),
        "window_days":      days,
        "pending_locks":    0,
        "deferred_corners": 0,
        "last_clean_run":   last_clean,
        "last_heartbeat":   last_heartbeat,
        "by_day": [
            {"date": r["d"], "settled_count": r["settled_count"], "pnl_zar": 0.0}
            for r in by_day
        ],
    }


# ---------------------------------------------------------------------------
# GET /reports/emit_market_breakdown
# ---------------------------------------------------------------------------

@router.get("/emit_market_breakdown")
def emit_market_breakdown(
    days: int = Query(30, ge=1, le=365),
    tier: str | None = Query(None),
) -> dict[str, Any]:
    """Per-(zone, bts, market, pick) hit rates across recent emits."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    tier_clause, tier_params = _tier_where_clause(tier)

    conn = get_conn(settings.sqlite_path)
    try:
        rows = conn.execute(
            f"""
            SELECT em.market, em.pick,
                   f.draw_odd, f.btts_yes_odd, f.btts_no_odd,
                   f.home_score, f.away_score, f.home_odd, f.away_odd, f.df_level
            FROM emit_log em
            JOIN fixtures f ON f.id = em.fixture_id
            LEFT JOIN leagues lg ON lg.id = f.league_id
            WHERE em.emitted_at >= ?{tier_clause}
            """,
            [cutoff.strftime("%Y-%m-%d %H:%M:%S"), *tier_params],
        ).fetchall()
        # V3.1 (2026-05-28): use V3_ACTIVE stone policy (the authoritative
        # promotion set the engine actually fires from), not a re-derivation
        # from live settled data. Fixes M4 (Session 15 process audit) — the
        # live-foundation approach required ~50+ settled picks per cell to
        # promote, so with current sample sizes every cell showed
        # `is_promoted=false` even though they were firing.
        from app.engine.static_policy import V3_ACTIVE
        live_promoted_keys: set[tuple[str, str, str]] = set(V3_ACTIVE.keys())
    finally:
        conn.close()

    buckets: dict[tuple[str, str, str, str, str], list[float]] = {}
    for r in rows:
        zone = zone_of(r["draw_odd"])
        bts = bts_of(r["btts_yes_odd"], r["btts_no_odd"])
        df = r["df_level"]  # backfilled from fixtures
        if zone is None or bts is None or df is None:
            continue
        outcome = settle_pick(r["market"], r["home_score"], r["away_score"],
                               r["home_odd"], r["away_odd"], r["pick"])
        if outcome is None:
            continue
        key = (zone, df, bts, r["market"], r["pick"])
        buckets.setdefault(key, []).append(outcome)

    cells: dict[tuple[str, str, str], dict[str, Any]] = {}
    for (zone, df, bts, market, pick), outs in sorted(buckets.items()):
        wins = sum(1 for o in outs if o == 1.0)
        voids = sum(1 for o in outs if o == 0.5)
        n = len(outs)
        hit_rate = (wins + 0.5 * voids) / n if n > 0 else None
        cell = cells.setdefault((zone, df, bts), {
            "zone": zone,
            "df": df,
            "bts_v2": bts,
            "partition_key": f"{zone}:{df}:{bts}",
            "is_promoted": (zone, df, bts) in live_promoted_keys,
            "markets": [],
        })
        cell["markets"].append({
            "market":   market,
            "pick":     pick,
            "n":        n,
            "wins":     wins,
            "voids":    voids,
            "losses":   n - wins - voids,
            "hit_rate": round(hit_rate * 100, 1) if hit_rate is not None else None,
        })

    return {
        "as_of":       datetime.now(tz=timezone.utc).isoformat(),
        "window_days": days,
        "tier":        tier,
        "cells":       list(cells.values()),
    }


# ---------------------------------------------------------------------------
# GET /reports/paper_trading.csv
# ---------------------------------------------------------------------------

@router.get("/paper_trading.csv")
def paper_trading_csv(
    days: int = Query(7, ge=1, le=14),
) -> StreamingResponse:
    """CSV of current picks window for paper trading."""
    from app.api.routes_picks import picks as picks_fn
    result = picks_fn(days=days)
    picks_data = result.get("picks", [])

    columns = [
        "fixture_id", "kickoff_utc", "home_team", "away_team",
        "league", "country", "tier",
        "market", "pick", "pick_odd", "pick_class",
        "partition_key", "draw_zone",
        "cell_historical_hit", "cell_historical_n",
        # operator-filled
        "sportybet_price", "hollywoodbet_price", "gbets_price",
        "chosen_bookmaker", "chosen_price",
        "decision", "pass_reason",
        "outcome", "notes",
    ]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for p in picks_data:
        row = {**p}
        for col in ["sportybet_price", "hollywoodbet_price", "gbets_price",
                    "chosen_bookmaker", "chosen_price", "decision",
                    "pass_reason", "outcome", "notes"]:
            row[col] = ""
        writer.writerow({k: row.get(k, "") for k in columns})

    today = datetime.now(tz=timezone.utc).date().isoformat()
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="oddsflow_picks_{today}.csv"'},
    )
