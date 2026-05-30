"""OddsFlow V4 — Inspector endpoints (partition_drift, recent_settled, daily_calendar)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.api.routes_picks import settle_pick, is_hit
from app.db.database import get_conn
from app.engine.classify import zone_of, bts_yesno
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
    """Simple gap-based drift verdict matching V3 / Session 11 convention.

    no_data  : recent sample < min_n (default 10)
    drifting : recent rate >= 10pp below historical baseline
    watch    : recent rate >= 5pp below historical baseline
    stable   : within 5pp of historical baseline (positive deltas included)

    Hit rate inputs use V3 non-loss rate (DNB voids count as wins) — see
    `routes_picks.is_hit`.
    """
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
    """Return the promoted cell set (ground-zero policy, 2-key).

    Re-Foundation — partition is ``(zone, bts_pocket)``. DF is a signal, not a
    cell axis; drift is computed per (zone, bts). Uses PROMOTED_CELLS directly.
    """
    return dict(PROMOTED_CELLS)


def compute_drift_rows(
    conn: sqlite3.Connection,
    *,
    recent_days: int = 30,
    min_sample_n: int = DRIFT_MIN_N,
) -> list[dict[str, Any]]:
    """Drift per live-promoted cell: historical hit vs recent emit_log (3-key).

    Bundle 6 (Session 23d) — adaptive window. Sparse cells that don't hit
    ``min_sample_n`` inside ``recent_days`` expand their lookup window in
    15-day steps up to 90 days. Stops rare zones (DF0 in low, strong_under
    in standard etc.) from being permanently invisible as ``no_data``.
    The ``window_days`` field on each row tells the operator which window
    the comparison ended up using.
    """
    live_promoted = _get_live_promoted(conn)
    expanded_windows = sorted({recent_days, 45, 60, 75, 90})

    # Pull the longest window once; bucket per cell with both n_per_window
    # and hits_per_window so the per-cell pass can pick the smallest window
    # that satisfies min_sample_n.
    longest = max(expanded_windows)
    cutoff_long = (datetime.now(tz=timezone.utc) - timedelta(days=longest)).strftime("%Y-%m-%d %H:%M:%S")
    recent_rows = conn.execute(
        """
        SELECT em.zone, em.df_level, em.bts_pocket, em.market, em.pick,
               em.emitted_at,
               f.home_score, f.away_score, f.home_odd, f.away_odd,
               fs.total_corners
        FROM emit_log em
        JOIN fixtures f ON f.id = em.fixture_id
        LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
        WHERE em.emitted_at >= ?
          AND f.home_score IS NOT NULL AND f.away_score IS NOT NULL
        """,
        (cutoff_long,),
    ).fetchall()

    now_utc = datetime.now(tz=timezone.utc)
    # Per-cell -> {window_days: {hits, n}}. 2-key (zone, bts) — df is a signal.
    per_cell: dict[tuple[str, str], dict[int, dict[str, int]]] = {}
    for r in recent_rows:
        key = (r["zone"], r["bts_pocket"])
        if key not in live_promoted:
            continue
        h = is_hit(settle_pick(r["market"], r["home_score"], r["away_score"],
                                r["home_odd"], r["away_odd"], r["pick"],
                                total_corners=r["total_corners"]))
        if h is None:
            continue
        try:
            ts = datetime.fromisoformat((r["emitted_at"] or "").replace(" ", "T"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_days = (now_utc - ts).days
        except Exception:
            continue
        for w in expanded_windows:
            if age_days <= w:
                slot = per_cell.setdefault(key, {}).setdefault(w, {"hits": 0, "n": 0})
                slot["hits"] += h
                slot["n"] += 1

    rows: list[dict[str, Any]] = []
    for (zone, bts), cell in sorted(live_promoted.items()):
        hist_pct = cell["threeway_hit"]
        hist_n = cell.get("n_fixtures", cell.get("n", 0))
        windows_for_cell = per_cell.get((zone, bts), {})
        # Smallest window meeting min_sample_n; fall back to base window.
        chosen_window = recent_days
        chosen_data = windows_for_cell.get(recent_days, {"hits": 0, "n": 0})
        if chosen_data["n"] < min_sample_n:
            for w in expanded_windows:
                d = windows_for_cell.get(w, {"hits": 0, "n": 0})
                if d["n"] >= min_sample_n:
                    chosen_window = w
                    chosen_data = d
                    break
            else:
                # None hit min_sample_n — return the longest window's data
                # rather than zeros so the operator can still see the count.
                chosen_window = longest
                chosen_data = windows_for_cell.get(longest, {"hits": 0, "n": 0})
        r_n = chosen_data["n"]
        r_hit = round(chosen_data["hits"] / r_n * 100, 1) if r_n > 0 else None
        gap_pp = round(r_hit - hist_pct, 1) if r_hit is not None else None
        flag = _drift_flag(gap_pp, r_n, min_sample_n)
        rows.append({
            "zone":           zone,
            "bts_v2":         bts,
            "partition_key":  f"{zone}:{bts}",
            "historical_n":   hist_n,
            "historical_hit": hist_pct,
            "recent_n":       r_n,
            "recent_hit":     r_hit,
            "window_days":    chosen_window,
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
                   em.zone AS em_zone, em.df_level AS em_df, em.bts_pocket AS em_bts,
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
        em_zone = r["em_zone"]; em_bts = r["em_bts"]
        em_df = r["em_df"] if "em_df" in r.keys() else None
        if em_df:
            pk = f"{em_zone}:{em_df}:{em_bts}" if (em_zone and em_bts) else None
        else:
            pk = f"{em_zone}:{em_bts}" if (em_zone and em_bts) else None
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
            "partition_key": pk,
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
    df:   str | None = Query(None),
    bts:  str | None = Query(None),
    fixture_id: int | None = Query(None),
    limit: int = Query(50, ge=5, le=200),
) -> dict[str, Any]:
    """Historical settled fixtures in the same (zone, bts) cell — 2-key.

    DF is a signal, not part of the cell; ``df`` is accepted but no longer
    required or filtered on (the similar set is the whole (zone, bts) cell).
    """
    conn = get_conn(settings.sqlite_path)
    try:
        if fixture_id is not None:
            fx = conn.execute(
                "SELECT draw_odd, btts_yes_odd, btts_no_odd, home_odd, away_odd FROM fixtures WHERE id=?",
                (fixture_id,),
            ).fetchone()
            if fx:
                zone = zone_of(fx["draw_odd"])
                bts  = bts_yesno(fx["btts_yes_odd"], fx["btts_no_odd"])

        if not zone or not bts:
            return {"error": "zone and bts required (or a valid fixture_id)", "fixtures": []}

        # Similar fixtures: the whole (zone, bts) cell. fixtures.bts_pocket stores the
        # legacy 4-pocket, so we filter the v4 bts (over/under) in Python from BTTS odds.
        rows = conn.execute("""
            SELECT f.id, f.date, f.home_team_name, f.away_team_name,
                   f.home_score, f.away_score, f.home_odd, f.away_odd, f.draw_odd,
                   f.btts_yes_odd, f.btts_no_odd,
                   lg.name AS league_name,
                   em.pick_uuid, em.market, em.pick, pr.outcome
            FROM fixtures f
            LEFT JOIN leagues lg      ON lg.id = f.league_id
            LEFT JOIN emit_log em     ON em.fixture_id = f.id
            LEFT JOIN pick_results pr ON pr.pick_uuid = em.pick_uuid
            WHERE f.home_score IS NOT NULL
              AND f.draw_zone  = ?
            ORDER BY f.date DESC
            LIMIT ?
        """, (zone, limit * 4)).fetchall()
        rows = [r for r in rows if bts_yesno(r["btts_yes_odd"], r["btts_no_odd"]) == bts][:limit]
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
        tw_green = alpha_wins or draw   # ground-zero alpha-or-draw, all zones

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
        "partition_key": f"{zone}:{bts}",
        "threeway_pick": "Alpha Win or Draw",
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
