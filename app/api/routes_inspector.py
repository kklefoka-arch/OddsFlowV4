"""OddsFlow V4 — Inspector endpoints (partition_drift, recent_settled, daily_calendar)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.api.routes_picks import settle_pick
from app.db.database import get_conn
from app.engine.classify import zone_of, bts_of
from app.engine.foundation import load_foundation
from app.engine.promotion import compute_foundation, PROMOTE, PROMOTE_TOLERANCE
from app.engine.static_policy import PROMOTED_CELLS
from app.settings import settings

router = APIRouter(prefix="/inspector", tags=["inspector"])

DRIFT_MIN_N = 10


# ---------------------------------------------------------------------------
# Drift helpers (exported for use by routes_diagnostics)
# ---------------------------------------------------------------------------

def _drift_flag(gap_pp: float | None, recent_n: int, min_n: int = DRIFT_MIN_N) -> str:
    if recent_n < min_n:
        return "no_data"
    if gap_pp is None:
        return "no_data"
    if gap_pp <= -10:
        return "drifting"
    if gap_pp <= -5:
        return "watch"
    return "stable"


def _get_live_promoted(conn: sqlite3.Connection) -> dict[tuple[str, str], dict[str, Any]]:
    """Build promoted cell dict from live foundation. Falls back to PROMOTED_CELLS on error."""
    try:
        foundation_rows = load_foundation(conn)
        foundation = compute_foundation(foundation_rows)
        return {
            (c["zone"], c["bts_pocket"]): c
            for c in foundation["all"]
            if c["threeway_promote"] in (PROMOTE, PROMOTE_TOLERANCE) and c["zone"] != "low"
        }
    except Exception:
        return dict(PROMOTED_CELLS)


def compute_drift_rows(
    conn: sqlite3.Connection,
    *,
    recent_days: int = 30,
    min_sample_n: int = DRIFT_MIN_N,
) -> list[dict[str, Any]]:
    """Drift for each live-promoted cell: live-foundation historical hit vs recent emit_log."""
    live_promoted = _get_live_promoted(conn)
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=recent_days)).strftime("%Y-%m-%d %H:%M:%S")

    recent_rows = conn.execute(
        """
        SELECT em.zone, em.bts_pocket, em.market, em.pick,
               f.home_score, f.away_score, f.home_odd, f.away_odd
        FROM emit_log em
        JOIN fixtures f ON f.id = em.fixture_id
        WHERE em.emitted_at >= ?
          AND f.home_score IS NOT NULL AND f.away_score IS NOT NULL
        """,
        (cutoff,),
    ).fetchall()

    recent: dict[tuple[str, str], dict[str, float]] = {}
    for r in recent_rows:
        key = (r["zone"], r["bts_pocket"])
        if key not in live_promoted:
            continue
        outcome = settle_pick(r["market"], r["home_score"], r["away_score"],
                               r["home_odd"], r["away_odd"], r["pick"])
        if outcome is None:
            continue
        if key not in recent:
            recent[key] = {"hits": 0.0, "n": 0}
        recent[key]["hits"] += outcome
        recent[key]["n"] += 1

    rows: list[dict[str, Any]] = []
    for (zone, bts), cell in sorted(live_promoted.items()):
        hist_pct = cell["threeway_hit"]
        hist_n = cell.get("n_fixtures", cell.get("n", 0))
        rec = recent.get((zone, bts), {"hits": 0.0, "n": 0})
        r_n = rec["n"]
        r_hit = round(rec["hits"] / r_n * 100, 1) if r_n > 0 else None
        gap_pp = round(r_hit - hist_pct, 1) if r_hit is not None else None
        flag = _drift_flag(gap_pp, r_n, min_sample_n)
        rows.append({
            "zone":           zone,
            "bts_v2":         bts,
            "historical_n":   hist_n,
            "historical_hit": hist_pct,
            "recent_n":       r_n,
            "recent_hit":     r_hit,
            "gap_pp":         gap_pp,
            "flag":           flag,
        })
    return rows


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/partition_drift")
def partition_drift(
    recent_days: int = Query(30, ge=1, le=365),
    min_sample_n: int = Query(DRIFT_MIN_N, ge=1, le=1000),
) -> dict[str, Any]:
    """For each PROMOTE cell: historical (stone policy) vs recent hit-rate + drift flag."""
    conn = get_conn(settings.sqlite_path)
    try:
        rows = compute_drift_rows(conn, recent_days=recent_days, min_sample_n=min_sample_n)
    finally:
        conn.close()

    return {
        "as_of":        datetime.now(tz=timezone.utc).isoformat(),
        "recent_days":  recent_days,
        "min_sample_n": min_sample_n,
        "rows":         rows,
        "summary": {
            "stable":   sum(1 for r in rows if r["flag"] == "stable"),
            "watch":    sum(1 for r in rows if r["flag"] == "watch"),
            "drifting": sum(1 for r in rows if r["flag"] == "drifting"),
            "no_data":  sum(1 for r in rows if r["flag"] == "no_data"),
        },
    }


@router.get("/recent_settled")
def recent_settled(
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    """Recent settled pick_results grouped by fixture."""
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn(settings.sqlite_path)
    try:
        rows = conn.execute(
            """
            SELECT pr.pick_uuid, pr.settled_at, pr.outcome, pr.actual_value,
                   em.fixture_id, em.market, em.pick, em.pick_odd,
                   f.date AS kickoff_utc, f.home_score, f.away_score,
                   lg.name AS league_name, lg.country, lg.tier,
                   th.name AS home_team, ta.name AS away_team
            FROM pick_results pr
            JOIN emit_log em ON em.pick_uuid = pr.pick_uuid
            JOIN fixtures f  ON f.id = em.fixture_id
            LEFT JOIN leagues lg ON lg.id = f.league_id
            LEFT JOIN teams th ON th.id = f.home_team_id
            LEFT JOIN teams ta ON ta.id = f.away_team_id
            WHERE pr.settled_at >= ?
            ORDER BY f.date DESC, pr.settled_at DESC
            """,
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()

    fixtures_by_id: dict[int, dict[str, Any]] = {}
    for r in rows:
        fx_id = r["fixture_id"]
        fx = fixtures_by_id.setdefault(fx_id, {
            "fixture_id":    fx_id,
            "kickoff_utc":   r["kickoff_utc"],
            "league":        r["league_name"],
            "country":       r["country"],
            "tier":          r["tier"],
            "home_team":     r["home_team"],
            "away_team":     r["away_team"],
            "home_score":    r["home_score"],
            "away_score":    r["away_score"],
            "home_corners":  None,
            "away_corners":  None,
            "partition_key": None,
            "picks":         [],
            "totals":        {"stake_zar": 0.0, "pnl_zar": 0.0,
                              "wins": 0, "half_wins": 0, "losses": 0},
        })
        ov = r["actual_value"]
        lbl = r["outcome"] or (
            "WIN" if ov == 1.0 else "VOID" if ov == 0.5 else
            "LOSS" if ov == 0.0 else "PENDING"
        )
        fx["picks"].append({
            "lock_id":            r["pick_uuid"],
            "market":             r["market"],
            "pick":               r["pick"],
            "price_taken":        r["pick_odd"],
            "settlement_outcome": ov,
            "outcome_label":      lbl,
            "pnl_zar":            None,
        })
        if ov == 1.0:   fx["totals"]["wins"]      += 1
        elif ov == 0.5: fx["totals"]["half_wins"] += 1
        elif ov == 0.0: fx["totals"]["losses"]    += 1

    fixtures = sorted(fixtures_by_id.values(),
                      key=lambda fx: fx["kickoff_utc"] or "", reverse=True)
    return {
        "as_of":          datetime.now(tz=timezone.utc).isoformat(),
        "window_days":    days,
        "fixtures_count": len(fixtures),
        "picks_count":    sum(len(fx["picks"]) for fx in fixtures),
        "totals": {
            "stake_zar": 0.0,
            "pnl_zar":   0.0,
            "wins":      sum(fx["totals"]["wins"]       for fx in fixtures),
            "half_wins": sum(fx["totals"]["half_wins"]  for fx in fixtures),
            "losses":    sum(fx["totals"]["losses"]     for fx in fixtures),
        },
        "fixtures": fixtures,
    }


@router.get("/similar")
def similar(
    zone: str | None = Query(None),
    bts: str | None = Query(None),
    fixture_id: int | None = Query(None),
    limit: int = Query(50, ge=5, le=200),
) -> dict[str, Any]:
    """Historical settled fixtures in the same (zone, bts_pocket) cell. Pre-match context."""
    conn = get_conn(settings.sqlite_path)
    try:
        if fixture_id is not None:
            fx = conn.execute(
                "SELECT draw_odd, btts_yes_odd, btts_no_odd FROM fixtures WHERE id=?",
                (fixture_id,),
            ).fetchone()
            if fx:
                zone = zone_of(fx["draw_odd"])
                bts  = bts_of(fx["btts_yes_odd"], fx["btts_no_odd"])

        if not zone or not bts:
            return {"error": "zone and bts required (or a valid fixture_id)", "fixtures": []}

        rows = conn.execute("""
            SELECT f.id, f.date, f.home_team_name, f.away_team_name,
                   f.home_score, f.away_score, f.home_odd, f.away_odd, f.draw_odd,
                   lg.name AS league_name,
                   em.pick_uuid, em.market, em.pick, pr.outcome
            FROM fixtures f
            LEFT JOIN leagues lg      ON lg.id = f.league_id
            LEFT JOIN emit_log em     ON em.fixture_id = f.id
            LEFT JOIN pick_results pr ON pr.pick_uuid = em.pick_uuid
            WHERE f.home_score IS NOT NULL
              AND f.draw_zone  = ?
              AND f.bts_pocket = ?
            ORDER BY f.date DESC
            LIMIT ?
        """, (zone, bts, limit)).fetchall()
    finally:
        conn.close()

    # Compute inline threeway green per row for quick hit rate
    green = total = 0
    fx_map: dict[int, dict] = {}
    for r in rows:
        fid = r["id"]
        hs  = r["home_score"]
        aws = r["away_score"]
        h_odd = r["home_odd"]
        a_odd = r["away_odd"]
        alpha_home = (h_odd <= a_odd) if (h_odd and a_odd) else True
        alpha_wins = (hs > aws) if alpha_home else (aws > hs)
        draw = (hs == aws)
        tw_green = (alpha_wins or draw) if zone in ("strong", "standard") else alpha_wins

        if fid not in fx_map:
            total += 1
            if tw_green:
                green += 1
            fx_map[fid] = {
                "fixture_id":   fid,
                "date":         r["date"],
                "home_team":    r["home_team_name"],
                "away_team":    r["away_team_name"],
                "home_score":   hs,
                "away_score":   aws,
                "league":       r["league_name"],
                "tw_green":     tw_green,
                "picks":        [],
            }
        if r["pick_uuid"]:
            fx_map[fid]["picks"].append({
                "pick_uuid": r["pick_uuid"],
                "market":    r["market"],
                "pick":      r["pick"],
                "outcome":   r["outcome"],
            })

    hit_rate = round(green / total * 100, 1) if total else None
    return {
        "zone":          zone,
        "bts_pocket":    bts,
        "threeway_pick": "DNB (Alpha Win or Draw)" if zone in ("strong", "standard") else "Alpha Win",
        "sample_n":      total,
        "threeway_hit":  hit_rate,
        "fixtures":      list(fx_map.values()),
    }


@router.get("/daily_calendar")
def daily_calendar(
    days: int = Query(28, ge=7, le=84),
) -> dict[str, Any]:
    """Per-day win/void/loss tally from pick_results for calendar view."""
    now = datetime.now(tz=timezone.utc)
    today_date = now.date()
    start_date = today_date - timedelta(days=days - 1)

    conn = get_conn(settings.sqlite_path)
    try:
        rows = conn.execute(
            """
            SELECT settled_at, outcome
            FROM pick_results
            WHERE settled_at >= ?
            """,
            (start_date.strftime("%Y-%m-%d 00:00:00"),),
        ).fetchall()
    finally:
        conn.close()

    per_day: dict[str, dict[str, int]] = {}
    for r in rows:
        date_str = (r["settled_at"] or "")[:10]
        if not date_str:
            continue
        b = per_day.setdefault(date_str, {"wins": 0, "voids": 0, "losses": 0})
        o = r["outcome"]
        if o == "WIN":    b["wins"]   += 1
        elif o == "VOID": b["voids"]  += 1
        elif o == "LOSS": b["losses"] += 1

    days_out = []
    cur = start_date
    while cur <= today_date:
        date_str = cur.strftime("%Y-%m-%d")
        b = per_day.get(date_str, {"wins": 0, "voids": 0, "losses": 0})
        w, v, l = b["wins"], b["voids"], b["losses"]
        n = w + v + l
        dominant = ("none" if n == 0 else
                    "win"  if w > l and w > v else
                    "loss" if l > w and l > v else
                    "void" if v > w and v > l else "mixed")
        days_out.append({
            "date":     date_str,
            "weekday":  cur.weekday(),
            "wins":     w, "voids": v, "losses": l,
            "n":        n,
            "dominant": dominant,
            "is_today": (cur == today_date),
        })
        cur += timedelta(days=1)

    return {
        "as_of":       now.isoformat(),
        "window_days": days,
        "start_date":  start_date.strftime("%Y-%m-%d"),
        "end_date":    today_date.strftime("%Y-%m-%d"),
        "days":        days_out,
    }
