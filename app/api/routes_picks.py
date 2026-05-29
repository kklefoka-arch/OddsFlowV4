"""OddsFlow V4 -- Picks endpoint.

Picks fire from the V3 static policy (static_policy.V3_ACTIVE).
Markets per zone:
  strong    -> goals_nl (Over 1.5)
  standard  -> goals_nl (Over 1.5) + corners_nl (Over 8.5)
  low       -> dnb  [activated -- LOW_ZONE_SUPPRESS=False]
  one_sided -> alpha_win
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.db.database import get_conn
from app.engine.classify import classify_fixture
from app.engine.static_policy import V3_ACTIVE
from app.settings import settings

router = APIRouter(tags=["picks"])

DRIFT_MIN_N = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _alpha_is_home(home_odd: float | None, away_odd: float | None) -> bool:
    if home_odd is None or away_odd is None:
        return True
    return home_odd <= away_odd


def _derive_dnb_odd(home: float | None, draw: float | None, away: float | None) -> tuple[float | None, bool]:
    if home is None or draw is None or away is None:
        return None, False
    try:
        p_home = 1.0 / float(home)
        p_draw = 1.0 / float(draw)
        p_away = 1.0 / float(away)
    except (TypeError, ValueError, ZeroDivisionError):
        return None, False
    if p_draw >= 1:
        return None, False
    p_win = p_home if p_home >= p_away else p_away
    if p_win <= 0:
        return None, False
    return round((1.0 - p_draw) / p_win, 3), True


def is_hit(outcome: float | None) -> int | None:
    """V3 hit-rate convention: any non-loss counts as 1 (matches static_policy
    baselines computed via `if alpha_wins or draw: hits += 1`). Loss = 0.
    None when outcome is unknown. Use this for hit-rate aggregation; use the
    raw settle_pick output for PnL where voids really do return half a unit.
    """
    if outcome is None:
        return None
    return 1 if outcome > 0 else 0


def settle_pick(market: str, home_score: int | None, away_score: int | None,
                home_odd: float | None, away_odd: float | None,
                pick: str = "",
                total_corners: int | None = None) -> float | None:
    """Resolve a V4 pick against a settled fixture. Returns 1.0/0.5/0.0 or None.

    1.0 = win (stake returns full unit profit)
    0.5 = void (DNB draw — stake returned, half-unit credit for PnL purposes)
    0.0 = loss (stake lost)

    For HIT-RATE display, pipe this through `is_hit()` instead of summing
    directly — V3 baselines treat voids as non-losses (hits), not 0.5.

    Signature mirrors settle.py (the autonomous batch settler) so live read
    paths and the cron settler resolve picks identically. corners_nl picks
    return None when total_corners is missing (fixture_stats not populated
    yet) — the daily settle.py retries on the next run when corners arrive.
    """
    import re as _re
    if home_score is None or away_score is None:
        return None
    if market == "goals_nl":
        m = _re.match(r"Over (\d+\.5) Goals", pick or "")
        if not m:
            return None
        return 1.0 if (home_score + away_score) > float(m.group(1)) else 0.0
    if market == "corners_nl":
        m = _re.match(r"Over (\d+\.5) Corners", pick or "")
        if not m:
            return None
        if total_corners is None:
            return None
        return 1.0 if total_corners > float(m.group(1)) else 0.0
    if home_odd is None or away_odd is None:
        return None
    alpha_home = _alpha_is_home(home_odd, away_odd)
    alpha_wins = (home_score > away_score) if alpha_home else (away_score > home_score)
    draw = (home_score == away_score)
    if market == "dnb":
        return 1.0 if alpha_wins else (0.5 if draw else 0.0)
    if market == "alpha_win":
        return 1.0 if alpha_wins else 0.0
    return None


def make_pick_uuid(fixture_id: int, market: str, pick: str) -> str:
    return hashlib.sha256(f"{fixture_id}:{market}:{pick}".encode()).hexdigest()[:36]


def _compute_cell_drift(conn: sqlite3.Connection, zone: str, df: str, bts: str,
                         market: str, historical_pct: float,
                         recent_days: int = 30) -> dict[str, Any]:
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=recent_days)).strftime("%Y-%m-%d %H:%M:%S")
    # 3-key filter (V3.2). em.df_level may be NULL for legacy V3 rows; the
    # df condition matches the live partition.
    rows = conn.execute(
        """
        SELECT em.market, em.pick,
               f.home_score, f.away_score, f.home_odd, f.away_odd,
               fs.total_corners
        FROM emit_log em
        JOIN fixtures f ON f.id = em.fixture_id
        LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
        WHERE em.zone = ? AND em.df_level = ? AND em.bts_pocket = ? AND em.market = ?
          AND em.emitted_at >= ?
          AND f.home_score IS NOT NULL AND f.away_score IS NOT NULL
          AND f.home_odd IS NOT NULL AND f.away_odd IS NOT NULL
        """,
        (zone, df, bts, market, cutoff),
    ).fetchall()

    # V3 non-loss hit rate (matches static_policy baseline convention — voids
    # count as 1, not 0.5). See is_hit() docstring. corners_nl picks need
    # total_corners from fixture_stats join.
    hits = 0
    n = 0
    for r in rows:
        h = is_hit(settle_pick(r["market"], r["home_score"], r["away_score"],
                                r["home_odd"], r["away_odd"], r["pick"],
                                total_corners=r["total_corners"]))
        if h is not None:
            hits += h
            n += 1

    recent_hit = round(hits / n * 100, 1) if n > 0 else None
    gap_pp = round(recent_hit - historical_pct, 1) if recent_hit is not None else None

    if n < DRIFT_MIN_N:
        flag = "no_data"
    elif gap_pp is None:
        flag = "no_data"
    elif gap_pp <= -10:
        flag = "drifting"
    elif gap_pp <= -5:
        flag = "watch"
    else:
        flag = "stable"

    return {"flag": flag, "gap_pp": gap_pp, "recent_n": n, "recent_hit": recent_hit}


def write_emit_log(conn: sqlite3.Connection, emit_rows: list[dict]) -> dict[str, Any]:
    """Write picks to emit_log. INSERT OR IGNORE on pick_uuid (idempotent).

    - If the row already exists and pick_odd is NULL, backfill pick_odd.
    - If a different pick for the same (fixture_id, market) exists without a
      pick_results row, supersede it: delete the stale row first, then insert.
    """
    now_sql = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    new_count = 0
    skip_count = 0
    updated_count = 0
    for p in emit_rows:
        uuid = make_pick_uuid(p["fixture_id"], p["market"], p["pick"])
        conn.execute(
            """
            DELETE FROM emit_log
            WHERE fixture_id = ? AND market = ? AND pick_uuid != ?
              AND pick_uuid NOT IN (SELECT pick_uuid FROM pick_results)
            """,
            (p["fixture_id"], p["market"], uuid),
        )
        # df_level column populated from V3.2 partition (Session 23c — Rule 1
        # overridden). Historic rows kept NULL; new emits store DF0/DF1/DF2.
        result = conn.execute(
            """
            INSERT OR IGNORE INTO emit_log
              (pick_uuid, emitted_at, fixture_id, zone, df_level, bts_pocket, tier,
               market, pick, pick_odd, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid,
                now_sql,
                p["fixture_id"],
                p["zone"],
                p.get("df"),
                p["bts_pocket"],
                p.get("tier"),
                p["market"],
                p["pick"],
                p.get("pick_odd"),
                p.get("confidence"),
            ),
        )
        if result.rowcount > 0:
            new_count += 1
        else:
            if p.get("pick_odd") is not None:
                upd = conn.execute(
                    "UPDATE emit_log SET pick_odd = ? WHERE pick_uuid = ? AND pick_odd IS NULL",
                    (p["pick_odd"], uuid),
                )
                if upd.rowcount > 0:
                    updated_count += 1
                else:
                    skip_count += 1
            else:
                skip_count += 1
    conn.commit()
    return {"new": new_count, "skip": skip_count, "updated": updated_count}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/picks")
def picks(days: int = Query(3, ge=1, le=14)) -> dict[str, Any]:
    """Emit picks for upcoming fixtures in V3 active cells."""
    now = datetime.now(tz=timezone.utc)
    today = now.strftime("%Y-%m-%d")
    horizon = (now + timedelta(days=days)).strftime("%Y-%m-%d")

    conn = get_conn(settings.sqlite_path)
    try:
        rows = conn.execute(
            """
            SELECT f.id, f.date, f.tier,
                   f.home_odd, f.draw_odd, f.away_odd,
                   f.btts_yes_odd, f.btts_no_odd,
                   f.goals_over_15_odd,
                   f.corners_over_85_odd,
                   ht.name AS home_team, at2.name AS away_team,
                   lg.name AS league, lg.country, lg.tier AS league_tier
            FROM fixtures f
            LEFT JOIN teams ht  ON ht.id  = f.home_team_id
            LEFT JOIN teams at2 ON at2.id = f.away_team_id
            LEFT JOIN leagues lg ON lg.id = f.league_id
            WHERE f.home_score IS NULL
              AND f.date >= ?
              AND substr(f.date, 1, 10) <= ?
            ORDER BY f.date ASC
            """,
            (today, horizon),
        ).fetchall()

        drift_cache: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        picks_out: list[dict[str, Any]] = []
        emit_rows: list[dict[str, Any]] = []
        # skip_reasons keeps the legacy "unclassifiable" total for back-compat
        # with the SPA, and adds the operator-requested breakdown so the picks
        # tab can distinguish missing draw_odd from missing BTS odds from the
        # both_sided exclusion (draw_odd < 2.90).
        skip_reasons = {
            "unclassifiable":         0,
            "no_draw_odd":            0,
            "draw_under_290":         0,
            "no_bts_odds":            0,
            "no_ha_odds":             0,
            "partition_not_promoted": 0,
        }

        for row in rows:
            d = dict(row)
            clf = classify_fixture(d)
            zone = clf.get("zone")
            bts  = clf.get("bts_pocket")
            df   = clf.get("df")

            if zone is None or bts is None or df is None:
                skip_reasons["unclassifiable"] += 1
                # Granular reasons so the picks tab can show why.
                draw_odd = d.get("draw_odd")
                if draw_odd is None:
                    skip_reasons["no_draw_odd"] += 1
                elif draw_odd < 2.90:
                    skip_reasons["draw_under_290"] += 1
                if d.get("btts_yes_odd") is None or d.get("btts_no_odd") is None:
                    skip_reasons["no_bts_odds"] += 1
                if d.get("home_odd") is None or d.get("away_odd") is None:
                    skip_reasons["no_ha_odds"] += 1
                continue

            cell_markets = V3_ACTIVE.get((zone, df, bts))
            if cell_markets is None:
                skip_reasons["partition_not_promoted"] += 1
                continue

            tier     = d.get("league_tier") or d.get("tier")
            home_odd = d.get("home_odd")
            away_odd = d.get("away_odd")
            draw_odd = d.get("draw_odd")
            alpha_home = _alpha_is_home(home_odd, away_odd)
            alpha_team = (d.get("home_team") or "") if alpha_home else (d.get("away_team") or "")
            emitted_any = False

            for market, mkt_cfg in cell_markets.items():
                drift_key = (zone, df, bts, market)
                if drift_key not in drift_cache:
                    try:
                        drift_cache[drift_key] = _compute_cell_drift(
                            conn, zone, df, bts, market, mkt_cfg["hit"]
                        )
                    except Exception:
                        drift_cache[drift_key] = {
                            "flag": None, "gap_pp": None,
                            "recent_n": None, "recent_hit": None,
                        }
                drift = drift_cache[drift_key]

                # build pick label and odd
                if market == "goals_nl":
                    line     = mkt_cfg["line"]
                    odd_col  = mkt_cfg["odd_col"]
                    pick_label = f"Over {line} Goals"
                    pick_odd   = d.get(odd_col) if odd_col else None
                    derived    = False

                elif market == "corners_nl":
                    line     = mkt_cfg["line"]
                    odd_col  = mkt_cfg["odd_col"]
                    pick_label = f"Over {line} Corners"
                    pick_odd   = d.get(odd_col) if odd_col else None
                    derived    = False

                elif market == "dnb":
                    pick_label = alpha_team
                    pick_odd, derived = _derive_dnb_odd(home_odd, draw_odd, away_odd)

                elif market == "alpha_win":
                    pick_label = alpha_team
                    pick_odd   = round(min(home_odd, away_odd), 3) if (home_odd and away_odd) else None
                    derived    = False

                else:
                    continue

                picks_out.append({
                    "fixture_id":               d["id"],
                    "kickoff_utc":              d["date"],
                    "home_team":                d.get("home_team") or "",
                    "away_team":                d.get("away_team") or "",
                    "league":                   d.get("league") or "",
                    "country":                  d.get("country") or "",
                    "tier":                     tier,
                    "market":                   market,
                    "pick":                     pick_label,
                    "line":                     mkt_cfg.get("line"),
                    "pick_leg":                 None,
                    "pick_odd":                 pick_odd,
                    "pick_odd_derived":         derived,
                    "pick_class":               "promote",
                    "partition_key":            f"{zone}:{df}:{bts}",
                    "draw_zone":                zone,
                    "df":                       df,
                    "bts_pocket":               bts,
                    "cell_drift_flag":          drift["flag"],
                    "cell_drift_gap_pp":        drift["gap_pp"],
                    "cell_drift_recent_n":      drift["recent_n"],
                    "cell_historical_hit":      mkt_cfg["hit"],
                    "cell_historical_n":        mkt_cfg["n"],
                    "asian_alternative":        None,
                    "asian_corners_alternative": None,
                })
                emit_rows.append({
                    "fixture_id": d["id"],
                    "zone":       zone,
                    "df":         df,
                    "bts_pocket": bts,
                    "tier":       tier,
                    "market":     market,
                    "pick":       pick_label,
                    "pick_odd":   pick_odd,
                    "confidence": round(mkt_cfg["hit"] / 100, 4),
                })
                emitted_any = True

            if not emitted_any:
                skip_reasons["partition_not_promoted"] += 1

        emit_summary = write_emit_log(conn, emit_rows)

    finally:
        conn.close()

    fixture_ids = {p["fixture_id"] for p in picks_out}
    counts_by_market: dict[str, int] = {}
    counts_by_tier: dict[str, int] = {}
    for p in picks_out:
        counts_by_market[p["market"]] = counts_by_market.get(p["market"], 0) + 1
        # Tier label: int → "1"/"2"/"3", None → "untiered" (matches Reports tier filter).
        t = p.get("tier")
        tier_key = str(t) if t in (1, 2, 3) else "untiered"
        counts_by_tier[tier_key] = counts_by_tier.get(tier_key, 0) + 1

    return {
        "count":            len(picks_out),
        "fixtures_count":   len(fixture_ids),
        "counts_by_class":  {"promote": len(picks_out)},
        "counts_by_market": counts_by_market,
        "counts_by_leg":    {"single": len(picks_out)},
        "counts_by_tier":   counts_by_tier,
        "window_days":      days,
        "as_of":            now.isoformat(),
        "skip_reasons":     skip_reasons,
        "emit_log":         emit_summary,
        "picks":            picks_out,
    }


# /picks/prx9 retired (V3 restoration, Session 19) — dead route removed (no frontend caller).
