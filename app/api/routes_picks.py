"""OddsFlow V4 — Picks endpoint.

Picks fire from the live V3 Foundation Matrix (compute_foundation), not a
hardcoded stone policy. Market is derived from zone: DNB for strong/standard,
Alpha Win for one_sided. Low zone is suppressed (MEASURING).
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.db.database import get_conn
from app.engine.classify import classify_fixture
from app.engine.foundation import load_foundation
from app.engine.promotion import compute_foundation, PROMOTE, PROMOTE_TOLERANCE
from app.engine.natural_lines import natural_line
from app.settings import settings

router = APIRouter(tags=["picks"])

DRIFT_MIN_N = 10

# Zone → market mapping. Low zone is excluded (MEASURING).
_ZONE_MARKET: dict[str, str] = {
    "strong":    "dnb",
    "standard":  "dnb",
    "one_sided": "alpha_win",
}


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


def settle_pick(market: str, home_score: int | None, away_score: int | None,
                home_odd: float | None, away_odd: float | None) -> float | None:
    """Resolve a V4 pick against a settled fixture. Returns 1.0/0.5/0.0 or None."""
    if home_score is None or away_score is None or home_odd is None or away_odd is None:
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


def _compute_cell_drift(conn: sqlite3.Connection, zone: str, bts: str,
                         historical_pct: float, recent_days: int = 30) -> dict[str, Any]:
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=recent_days)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """
        SELECT em.market,
               f.home_score, f.away_score, f.home_odd, f.away_odd
        FROM emit_log em
        JOIN fixtures f ON f.id = em.fixture_id
        WHERE em.zone = ? AND em.bts_pocket = ?
          AND em.emitted_at >= ?
          AND f.home_score IS NOT NULL AND f.away_score IS NOT NULL
          AND f.home_odd IS NOT NULL AND f.away_odd IS NOT NULL
        """,
        (zone, bts, cutoff),
    ).fetchall()

    hits = 0.0
    n = 0
    for r in rows:
        outcome = settle_pick(r["market"], r["home_score"], r["away_score"],
                              r["home_odd"], r["away_odd"])
        if outcome is not None:
            hits += outcome
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
    """Write picks to emit_log, idempotent via INSERT OR IGNORE on pick_uuid."""
    now_sql = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    new_count = 0
    skip_count = 0
    for p in emit_rows:
        uuid = make_pick_uuid(p["fixture_id"], p["market"], p["pick"])
        result = conn.execute(
            """
            INSERT OR IGNORE INTO emit_log
              (pick_uuid, emitted_at, fixture_id, zone, bts_pocket, tier,
               market, pick, pick_odd, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid,
                now_sql,
                p["fixture_id"],
                p["zone"],
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
            skip_count += 1
    conn.commit()
    return {"new": new_count, "skip": skip_count}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/picks")
def picks(days: int = Query(3, ge=1, le=14)) -> dict[str, Any]:
    """Emit picks for upcoming fixtures in live promoted cells."""
    now = datetime.now(tz=timezone.utc)
    today = now.strftime("%Y-%m-%d")
    horizon = (now + timedelta(days=days)).strftime("%Y-%m-%d")

    conn = get_conn(settings.sqlite_path)
    try:
        # --- Build live promoted cell set from V3 Foundation Matrix ---
        foundation_rows = load_foundation(conn)
        foundation = compute_foundation(foundation_rows)

        promoted: dict[tuple[str, str], dict[str, Any]] = {}
        promoted_goals: dict[tuple[str, str], dict[str, Any]] = {}
        for cell in foundation["all"]:
            if cell["zone"] == "low":
                continue
            key = (cell["zone"], cell["bts_pocket"])
            if cell["threeway_promote"] in (PROMOTE, PROMOTE_TOLERANCE):
                promoted.setdefault(key, cell)
            if cell["goals_promote"] in (PROMOTE, PROMOTE_TOLERANCE):
                promoted_goals.setdefault(key, cell)

        # --- Fetch upcoming fixtures in window ---
        rows = conn.execute(
            """
            SELECT f.id, f.date, f.tier,
                   f.home_odd, f.draw_odd, f.away_odd,
                   f.btts_yes_odd, f.btts_no_odd,
                   f.goals_over_15_odd, f.goals_over_25_odd, f.goals_over_35_odd,
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

        drift_cache: dict[tuple[str, str], dict[str, Any]] = {}
        picks_out: list[dict[str, Any]] = []
        emit_rows: list[dict[str, Any]] = []
        skip_reasons = {"unclassifiable": 0, "partition_not_promoted": 0}

        for row in rows:
            d = dict(row)
            clf = classify_fixture(d)
            zone = clf.get("zone")
            bts = clf.get("bts_pocket")

            if zone is None or bts is None:
                skip_reasons["unclassifiable"] += 1
                continue

            tier = d.get("league_tier") or d.get("tier")
            home_odd = d.get("home_odd")
            away_odd = d.get("away_odd")
            draw_odd = d.get("draw_odd")
            alpha_home = _alpha_is_home(home_odd, away_odd)
            alpha_team = (d.get("home_team") or "") if alpha_home else (d.get("away_team") or "")
            emitted_any = False

            # --- Threeway pick (DNB / Alpha Win) ---
            cell = promoted.get((zone, bts))
            market = _ZONE_MARKET.get(zone)
            if cell is not None and market is not None:
                drift_key = (zone, bts)
                if drift_key not in drift_cache:
                    try:
                        drift_cache[drift_key] = _compute_cell_drift(
                            conn, zone, bts, cell["threeway_hit"]
                        )
                    except Exception:
                        drift_cache[drift_key] = {
                            "flag": None, "gap_pp": None, "recent_n": None, "recent_hit": None
                        }
                drift = drift_cache[drift_key]

                if market == "dnb":
                    pick_label = alpha_team
                    pick_odd, derived = _derive_dnb_odd(home_odd, draw_odd, away_odd)
                else:  # alpha_win
                    pick_label = alpha_team
                    pick_odd = round(min(home_odd, away_odd), 3) if (home_odd and away_odd) else None
                    derived = False

                picks_out.append({
                    "fixture_id":              d["id"],
                    "kickoff_utc":             d["date"],
                    "home_team":               d.get("home_team") or "",
                    "away_team":               d.get("away_team") or "",
                    "league":                  d.get("league") or "",
                    "country":                 d.get("country") or "",
                    "tier":                    tier,
                    "market":                  market,
                    "pick":                    pick_label,
                    "line":                    None,
                    "pick_leg":                None,
                    "pick_odd":                pick_odd,
                    "pick_odd_derived":        derived,
                    "pick_class":              "promote",
                    "partition_key":           f"{zone}:{bts}",
                    "draw_zone":               zone,
                    "cell_drift_flag":         drift["flag"],
                    "cell_drift_gap_pp":       drift["gap_pp"],
                    "cell_drift_recent_n":     drift["recent_n"],
                    "cell_historical_hit":     cell["threeway_hit"],
                    "cell_historical_n":       cell["n_fixtures"],
                    "asian_alternative":       None,
                    "asian_corners_alternative": None,
                })
                emit_rows.append({
                    "fixture_id": d["id"],
                    "zone":       zone,
                    "bts_pocket": bts,
                    "tier":       tier,
                    "market":     market,
                    "pick":       pick_label,
                    "pick_odd":   pick_odd,
                    "confidence": round(cell["threeway_hit"] / 100, 4),
                })
                emitted_any = True

            # --- Goals natural line pick ---
            goals_cell = promoted_goals.get((zone, bts))
            if goals_cell is not None:
                goals_line = natural_line(zone, "goals")
                goals_pick = f"Over {goals_line} Goals"
                _goals_odd_col = {1.5: "goals_over_15_odd", 2.5: "goals_over_25_odd", 3.5: "goals_over_35_odd"}
                goals_pick_odd = d.get(_goals_odd_col.get(goals_line, "")) or d.get("goals_over_25_odd")
                picks_out.append({
                    "fixture_id":              d["id"],
                    "kickoff_utc":             d["date"],
                    "home_team":               d.get("home_team") or "",
                    "away_team":               d.get("away_team") or "",
                    "league":                  d.get("league") or "",
                    "country":                 d.get("country") or "",
                    "tier":                    tier,
                    "market":                  "goals_nl",
                    "pick":                    goals_pick,
                    "line":                    goals_line,
                    "pick_leg":                None,
                    "pick_odd":                goals_pick_odd,
                    "pick_odd_derived":        False,
                    "pick_class":              "promote",
                    "partition_key":           f"{zone}:{bts}",
                    "draw_zone":               zone,
                    "cell_drift_flag":         None,
                    "cell_drift_gap_pp":       None,
                    "cell_drift_recent_n":     None,
                    "cell_historical_hit":     goals_cell["gn_hit"],
                    "cell_historical_n":       goals_cell["n_fixtures"],
                    "asian_alternative":       None,
                    "asian_corners_alternative": None,
                })
                emit_rows.append({
                    "fixture_id": d["id"],
                    "zone":       zone,
                    "bts_pocket": bts,
                    "tier":       tier,
                    "market":     "goals_nl",
                    "pick":       goals_pick,
                    "pick_odd":   goals_pick_odd,
                    "confidence": round(goals_cell["gn_hit"] / 100, 4),
                })
                emitted_any = True

            if not emitted_any:
                skip_reasons["partition_not_promoted"] += 1

        emit_summary = write_emit_log(conn, emit_rows)

    finally:
        conn.close()

    fixture_ids = {p["fixture_id"] for p in picks_out}
    counts_by_market: dict[str, int] = {}
    for p in picks_out:
        counts_by_market[p["market"]] = counts_by_market.get(p["market"], 0) + 1

    return {
        "count":            len(picks_out),
        "fixtures_count":   len(fixture_ids),
        "counts_by_class":  {"promote": len(picks_out)},
        "counts_by_market": counts_by_market,
        "counts_by_leg":    {"single": len(picks_out)},
        "counts_by_tier":   {},
        "window_days":      days,
        "as_of":            now.isoformat(),
        "skip_reasons":     skip_reasons,
        "emit_log":         emit_summary,
        "picks":            picks_out,
    }


@router.get("/picks/prx9")
def picks_prx9(
    days: int = Query(3, ge=1, le=14),
    min_rank: int = Query(4, ge=2, le=8),
    combo_size: int = Query(5, ge=3, le=15),
) -> dict[str, Any]:
    """PRX9 is retired in V4. Returns empty."""
    return {
        "count": 0,
        "window_days": days,
        "min_rank_filter": min_rank,
        "as_of": datetime.now(tz=timezone.utc).isoformat(),
        "signal_bounds": {},
        "emit_log": {"new": 0, "skip": 0},
        "picks": [],
        "system_combinations": [],
    }
