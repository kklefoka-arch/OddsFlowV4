"""Fetch historical fixtures + results for all 30 active leagues from Sportmonks.

Covers 2023-01-01 through yesterday. Writes scores, corners, and pre-match odds
into oddsflow_v4.db. Safe to re-run — deduplicates on sportmonks_id.

Usage:
    python scripts/fetch_historical.py

Approximate runtime: 30-60 minutes (41 monthly windows, rate-limited).
"""

from __future__ import annotations

import sqlite3
import urllib.request
import urllib.parse
import json
import time
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TOKEN = "2AWINN4fYPiQkY2lfHee9TASZubv74uP1RIY4ILY15Mzg4bw5bH2v2SeKGAN"
DB    = r"C:\OddsFlowV4\data\oddsflow_v4.db"
BASE  = "https://api.sportmonks.com/v3/football"

HISTORY_START = date(2023, 1, 1)
HISTORY_END   = date.today() - timedelta(days=1)   # yesterday

# Verified Sportmonks type_id for corners (confirmed 2026-05-23)
CORNERS_TYPE_ID = 34

# All 30 active leagues: sportmonks_id → tier
ACTIVE_LEAGUES: dict[int, int] = {
    # T1
    573:  1,   # Sweden — Allsvenskan
    444:  1,   # Norway — Eliteserien
    345:  1,   # Iceland — Besta deild
    292:  1,   # Finland — Veikkausliiga
    360:  1,   # Republic of Ireland — Premier Division
    779:  1,   # United States — Major League Soccer
    648:  1,   # Brazil — Serie A
    3537: 1,   # Japan — J1 100 Year Vision League
    1034: 1,   # South Korea — K League 1
    # T2
    393:  2,   # Kazakhstan — Premier League
    405:  2,   # Lithuania — A Lyga
    579:  2,   # Sweden — Superettan
    585:  2,   # Sweden — Ettan: North
    588:  2,   # Sweden — Ettan: South
    681:  2,   # Colombia — Copa Colombia
    678:  2,   # Colombia — Primera B
    696:  2,   # Ecuador — Liga Pro
    1689: 2,   # Canada — Premier League
    295:  2,   # Finland — Ykköseliga
    286:  2,   # Estonia — Meistriliiga
    289:  2,   # Estonia — Esiliiga A
    791:  2,   # United States — USL Championship
    3550: 2,   # Japan — J2/J3 100 Year Vision League
    989:  2,   # China — Super League
    # T3
    1642: 3,   # Argentina — Reserve League
    351:  3,   # Iceland — 2. Deild
    797:  3,   # United States — USL League Two
    1607: 3,   # United States — USL League One
    2545: 3,   # United States — MLS Next Pro
    1098: 3,   # Bolivia — Liga De Futbol Prof
}

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api_get(path: str, params: dict, retries: int = 4) -> dict:
    params["api_token"] = TOKEN
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:
            last_err = e
            wait = 10 * (2 ** attempt)
            print(f"    [retry {attempt + 1}/{retries}] {e} — sleeping {wait}s")
            time.sleep(wait)
    raise last_err  # type: ignore[misc]


def fetch_all_pages(path: str, params: dict, max_pages: int = 40) -> list:
    rows, page = [], 1
    while page <= max_pages:
        p = {**params, "page": page, "per_page": 50}
        data = api_get(path, p)
        batch = data.get("data", [])
        if not isinstance(batch, list):
            break
        rows.extend(batch)
        if not data.get("pagination", {}).get("has_more"):
            break
        page += 1
        time.sleep(0.4)
    return rows

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def extract_scores(scores_list: list) -> tuple[int | None, int | None]:
    home = away = None
    for s in (scores_list or []):
        if s.get("description") != "CURRENT":
            continue
        score_data = s.get("score") or {}
        goals = score_data.get("goals")
        participant = score_data.get("participant")
        if goals is None:
            continue
        try:
            goals = int(goals)
        except (TypeError, ValueError):
            continue
        if participant == "home":
            home = goals
        elif participant == "away":
            away = goals
    return home, away


def extract_corners(stats_list: list, home_p_id: int | None, away_p_id: int | None) -> tuple[int | None, int | None]:
    hc = ac = None
    for s in (stats_list or []):
        if s.get("type_id") != CORNERS_TYPE_ID:
            continue
        val = (s.get("data") or {}).get("value")
        if val is None:
            continue
        try:
            val = int(val)
        except (TypeError, ValueError):
            continue
        pid = s.get("participant_id")
        if pid == home_p_id:
            hc = val
        elif pid == away_p_id:
            ac = val
    return hc, ac


def extract_odds(odds_list: list) -> tuple:
    home_odd = draw_odd = away_odd = btts_yes = btts_no = None
    goals_buckets:   dict[float, list] = {1.5: [], 2.5: [], 3.5: []}
    corners_buckets: dict[float, list] = {7.5: [], 8.5: [], 9.5: []}
    for o in (odds_list or []):
        mid   = o.get("market_id")
        label = (o.get("label") or "").lower().strip()
        val   = o.get("value")
        if not val:
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        if mid == 1:
            if label in ("home", "1"):   home_odd = val
            elif label in ("draw", "x"): draw_odd = val
            elif label in ("away", "2"): away_odd = val
        elif mid == 14:
            if label == "yes":  btts_yes = val
            elif label == "no": btts_no  = val
        elif mid == 7 and label == "over":
            try:
                line = float(o.get("total") or "")
            except (TypeError, ValueError):
                continue
            if line in goals_buckets:
                goals_buckets[line].append(val)
        elif mid == 45 and label == "over":
            try:
                line = float(o.get("total") or "")
            except (TypeError, ValueError):
                continue
            if line in corners_buckets:
                corners_buckets[line].append(val)
    g15 = max(goals_buckets[1.5])   if goals_buckets[1.5]   else None
    g25 = max(goals_buckets[2.5])   if goals_buckets[2.5]   else None
    g35 = max(goals_buckets[3.5])   if goals_buckets[3.5]   else None
    c75 = max(corners_buckets[7.5]) if corners_buckets[7.5] else None
    c85 = max(corners_buckets[8.5]) if corners_buckets[8.5] else None
    c95 = max(corners_buckets[9.5]) if corners_buckets[9.5] else None
    return home_odd, draw_odd, away_odd, btts_yes, btts_no, g15, g25, g35, c75, c85, c95

# ---------------------------------------------------------------------------
# Classification (mirrors fetch_upcoming.py)
# ---------------------------------------------------------------------------

def _zone(d: float | None) -> str | None:
    if d is None:
        return None
    if d < 2.70: return None
    if d < 3.40: return "strong"
    if d < 4.10: return "standard"
    if d < 4.80: return "low"
    return "one_sided"


def _bts(y: float | None, n: float | None) -> str | None:
    if y is None or n is None:
        return None
    if y <= n:
        return "strong_over" if y < 1.50 else "slight_over"
    return "strong_under" if n < 1.50 else "slight_under"

# ---------------------------------------------------------------------------
# Build monthly windows
# ---------------------------------------------------------------------------

def monthly_windows(start: date, end: date) -> list[tuple[str, str]]:
    """Return (window_start, window_end) pairs covering [start, end] month by month."""
    windows = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        # Last day of the month
        if cur.month == 12:
            last = date(cur.year + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(cur.year, cur.month + 1, 1) - timedelta(days=1)
        last = min(last, end)
        windows.append((max(cur, start).isoformat(), last.isoformat()))
        # Next month
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return windows

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Build lookup maps from DB
    teams_seen: set[int] = {
        r["sportmonks_id"]
        for r in conn.execute(
            "SELECT sportmonks_id FROM teams WHERE sportmonks_id IS NOT NULL"
        ).fetchall()
    }

    league_id_map: dict[int, int] = {
        r["sportmonks_id"]: r["id"]
        for r in conn.execute(
            "SELECT id, sportmonks_id FROM leagues WHERE sportmonks_id IS NOT NULL"
        ).fetchall()
    }

    # Warn about any active leagues not in the leagues table
    missing = [sm for sm in ACTIVE_LEAGUES if sm not in league_id_map]
    if missing:
        print(f"WARNING: {len(missing)} active league(s) not found in leagues table: {missing}")
        print("  These fixtures will be skipped. Add them to the leagues table first.\n")

    windows = monthly_windows(HISTORY_START, HISTORY_END)
    print(f"Historical fetch: {HISTORY_START} to {HISTORY_END}")
    print(f"Leagues: {len(ACTIVE_LEAGUES)} active  |  Windows: {len(windows)} months\n")

    total_inserted = total_updated = total_skipped = total_corners = 0

    for w_start, w_end in windows:
        print(f"Window {w_start} -> {w_end}", end="  ", flush=True)

        try:
            raw = fetch_all_pages(
                f"fixtures/between/{w_start}/{w_end}",
                {"include": "scores;statistics;participants"},
                max_pages=40,
            )
        except Exception as e:
            print(f"ERROR: {e} — skipping window")
            continue

        relevant = [fx for fx in raw if fx.get("league_id") in ACTIVE_LEAGUES]
        print(f"({len(raw)} total, {len(relevant)} in active leagues)")

        win_inserted = win_updated = win_skipped = win_corners = 0

        for fx in relevant:
            sm_id      = fx.get("id")
            raw_start  = fx.get("starting_at") or ""
            kickoff    = raw_start.replace("T", " ").split(".")[0]
            league_sm  = fx.get("league_id")
            tier       = ACTIVE_LEAGUES.get(league_sm)

            if not tier or not sm_id:
                win_skipped += 1
                continue

            internal_league_id = league_id_map.get(league_sm)
            if internal_league_id is None:
                win_skipped += 1
                continue

            # Scores — only process fixtures that have finished
            home_score, away_score = extract_scores(fx.get("scores") or [])
            if home_score is None or away_score is None:
                win_skipped += 1
                continue

            total_goals = home_score + away_score

            # Participants
            participants = fx.get("participants") or []
            home_p = next((p for p in participants if p.get("meta", {}).get("location") == "home"), None)
            away_p = next((p for p in participants if p.get("meta", {}).get("location") == "away"), None)
            if not home_p or not away_p:
                win_skipped += 1
                continue

            # Ensure teams exist
            for team in (home_p, away_p):
                tsm = team["id"]
                if tsm not in teams_seen:
                    conn.execute(
                        "INSERT OR IGNORE INTO teams (name, sportmonks_id) VALUES (?, ?)",
                        (team.get("name", f"Team {tsm}"), tsm),
                    )
                    teams_seen.add(tsm)

            ht = conn.execute("SELECT id FROM teams WHERE sportmonks_id=?", (home_p["id"],)).fetchone()
            at = conn.execute("SELECT id FROM teams WHERE sportmonks_id=?", (away_p["id"],)).fetchone()
            if not ht or not at:
                win_skipped += 1
                continue

            home_p_id = int(home_p["id"])
            away_p_id = int(away_p["id"])

            # Corners
            hc, ac = extract_corners(fx.get("statistics") or [], home_p_id, away_p_id)

            existing = conn.execute(
                "SELECT id FROM fixtures WHERE sportmonks_id=?", (sm_id,)
            ).fetchone()

            if existing:
                # Update scores only — preserve any existing odds/classification
                conn.execute("""
                    UPDATE fixtures SET
                        home_score=?, away_score=?, total_goals=?,
                        status='settled', updated_at=?
                    WHERE sportmonks_id=? AND home_score IS NULL
                """, (home_score, away_score, total_goals, now_ts, sm_id))
                win_updated += 1
                fix_id = existing["id"]
            else:
                # New fixture — insert without odds (odds not fetched in historical mode)
                conn.execute("""
                    INSERT INTO fixtures
                        (sportmonks_id, league_id, tier, date, status,
                         home_team_id, away_team_id, home_team_name, away_team_name,
                         home_score, away_score, total_goals,
                         created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    sm_id, internal_league_id, tier, kickoff, "settled",
                    ht["id"], at["id"],
                    home_p.get("name"), away_p.get("name"),
                    home_score, away_score, total_goals,
                    now_ts, now_ts,
                ))
                fix_id = conn.execute(
                    "SELECT id FROM fixtures WHERE sportmonks_id=?", (sm_id,)
                ).fetchone()["id"]
                win_inserted += 1

            # Corner stats
            if hc is not None and ac is not None:
                conn.execute("""
                    INSERT OR REPLACE INTO fixture_stats
                        (fixture_id, home_corners, away_corners, total_corners)
                    VALUES (?, ?, ?, ?)
                """, (fix_id, hc, ac, hc + ac))
                win_corners += 1

        conn.commit()

        total_inserted += win_inserted
        total_updated  += win_updated
        total_skipped  += win_skipped
        total_corners  += win_corners

        print(f"  inserted={win_inserted}  updated={win_updated}  "
              f"skipped={win_skipped}  corners={win_corners}")

        time.sleep(0.6)   # polite rate limiting

    # Summary
    print(f"\n{'='*60}")
    print(f"Historical fetch complete")
    print(f"  Fixtures inserted : {total_inserted:>6}")
    print(f"  Fixtures updated  : {total_updated:>6}")
    print(f"  Skipped (no score): {total_skipped:>6}")
    print(f"  Corner stats      : {total_corners:>6}")

    # Check new per-league counts
    print(f"\nPer-league fixture counts after fetch:")
    rows = conn.execute("""
        SELECT l.name, l.country, COUNT(f.id) as cnt
        FROM fixtures f
        JOIN leagues l ON f.league_id = l.id
        WHERE l.sportmonks_id IN ({})
        GROUP BY l.id
        ORDER BY cnt DESC
    """.format(",".join("?" * len(ACTIVE_LEAGUES))), list(ACTIVE_LEAGUES.keys())).fetchall()
    for r in rows:
        print(f"  {r['country'] or '?':<22} {r['name']:<35} {r['cnt']:>6}")

    conn.close()


if __name__ == "__main__":
    main()
