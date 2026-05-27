"""Fetch match results from Sportmonks and write to fixtures + fixture_stats.

Run after match days to update home_score, away_score, and corner stats
for fixtures that have been played but not yet settled in the DB.

What this closes:
  Phase 8 (Score Update) — Gap G1 in context/06_process_flow.md

After running this, run settle.py to write pick_results from emit_log.
"""
import sqlite3, urllib.request, urllib.parse, json, time
from datetime import date as date_cls, datetime, timedelta, timezone
from collections import defaultdict

# V3.1 (2026-05-28): prefer env override; fall back to literal for legacy.
import os as _os
TOKEN = _os.environ.get("SPORTMONKS_TOKEN", "2AWINN4fYPiQkY2lfHee9TASZubv74uP1RIY4ILY15Mzg4bw5bH2v2SeKGAN")
DB    = r"C:\OddsFlowV4\data\oddsflow_v4.db"
BASE  = "https://api.sportmonks.com/v3/football"

# Verified via API probe 2026-05-23: Shamrock Rovers 1-2 Sligo Rovers
# type_id=34 → corners (home=3, away=4 for that match)
CORNERS_TYPE_ID = 34

ACTIVE_LEAGUES = {
    # T1
    573, 444, 345, 292, 360, 779, 648, 3537, 1034,
    # T2
    393, 405, 579, 585, 588, 681, 678, 696, 1689, 295, 286, 289, 791, 3550, 989,
    # T3
    1642, 351, 797, 1607, 2545, 1098,
}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def api_get(path: str, params: dict, retries: int = 3) -> dict:
    """V3.1 (2026-05-28): retry on transient API failures (D13 in process audit).

    Backoff: 8s, 16s on first two retries. Matches fetch_upcoming.py pattern.
    """
    params["api_token"] = TOKEN
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                wait = 8 * (2 ** attempt)
                print(f"    [retry {attempt + 1}/{retries - 1}] {e} — sleeping {wait}s")
                time.sleep(wait)
    raise last_err  # type: ignore[misc]


def fetch_all(path: str, params: dict, max_pages: int = 20) -> list:
    rows, page = [], 1
    while page <= max_pages:
        p = {**params, "page": page, "per_page": 50}
        data = api_get(path, p)
        batch = data.get("data", [])
        if not isinstance(batch, list):
            break
        rows.extend(batch)
        print(f"    page {page}: {len(batch)} fixtures (total: {len(rows)})")
        if not data.get("pagination", {}).get("has_more"):
            break
        page += 1
        time.sleep(0.25)
    return rows


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def extract_scores(scores_list: list) -> tuple[int | None, int | None]:
    """Parse FT score from Sportmonks scores include.

    Uses description="CURRENT" entries — the running/final score at FT.
    Returns (home_score, away_score) or (None, None) if not available.
    """
    home_score = away_score = None
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
            home_score = goals
        elif participant == "away":
            away_score = goals
    return home_score, away_score


def extract_corners(stats_list: list, home_p_id: int, away_p_id: int) -> tuple[int | None, int | None]:
    """Parse corner stats from Sportmonks statistics include.

    type_id=34 = corners. Verified against a known match.
    Returns (home_corners, away_corners) — either may be None if not available.
    """
    home_corners = away_corners = None
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
            home_corners = val
        elif pid == away_p_id:
            away_corners = val
    return home_corners, away_corners


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_utc = datetime.now(timezone.utc)
today   = now_utc.strftime("%Y-%m-%d")
now_ts  = now_utc.strftime("%Y-%m-%d %H:%M:%S")

# Find all unsettled fixtures we can fetch results for:
# Must have a sportmonks_id (inserted by fetch_upcoming.py)
# Must be before today (match day has passed)
unsettled = conn.execute("""
    SELECT id, sportmonks_id, date, home_team_name, away_team_name
    FROM fixtures
    WHERE home_score IS NULL
      AND sportmonks_id IS NOT NULL
      AND substr(date, 1, 10) < ?
    ORDER BY date ASC
""", (today,)).fetchall()

print(f"Unsettled fixtures eligible for result fetch: {len(unsettled)}")
if not unsettled:
    conn.close()
    print("Nothing to fetch — run again after match days.")
    raise SystemExit(0)

# Quick lookup: sportmonks_id → DB row
sm_map: dict[int, sqlite3.Row] = {
    int(row["sportmonks_id"]): row for row in unsettled
}

# Group by week (Monday–Sunday) to minimise API calls
by_week: dict[str, list[sqlite3.Row]] = defaultdict(list)
for row in unsettled:
    date_str = (row["date"] or "")[:10]
    if not date_str:
        continue
    d = date_cls.fromisoformat(date_str)
    monday = d - timedelta(days=d.weekday())
    by_week[monday.isoformat()].append(row)

print(f"Grouped into {len(by_week)} week window(s)\n")

updated = inserted_stats = skipped_no_score = skipped_not_ours = 0

for week_start in sorted(by_week):
    week_rows = by_week[week_start]
    week_end  = (date_cls.fromisoformat(week_start) + timedelta(days=6)).isoformat()

    print(f"Window {week_start} to {week_end}  ({len(week_rows)} fixture(s) expected)")

    try:
        batch = fetch_all(
            f"fixtures/between/{week_start}/{week_end}",
            {"include": "scores;statistics;participants"},
        )
    except Exception as e:
        print(f"  API error: {e} — skipping window")
        continue

    relevant = [fx for fx in batch if fx.get("league_id") in ACTIVE_LEAGUES]
    print(f"  {len(batch)} from API, {len(relevant)} in active leagues")

    for fx in relevant:
        sm_id = fx.get("id")
        db_row = sm_map.get(int(sm_id)) if sm_id is not None else None
        if db_row is None:
            skipped_not_ours += 1
            continue

        home_score, away_score = extract_scores(fx.get("scores") or [])

        if home_score is None or away_score is None:
            # Match may not have finished (in-play, postponed, etc.)
            skipped_no_score += 1
            continue

        total_goals = home_score + away_score

        # Participant IDs for corner attribution
        participants = fx.get("participants") or []
        home_p_id = next(
            (int(p["id"]) for p in participants if p.get("meta", {}).get("location") == "home"),
            None
        )
        away_p_id = next(
            (int(p["id"]) for p in participants if p.get("meta", {}).get("location") == "away"),
            None
        )

        home_corners, away_corners = None, None
        if home_p_id and away_p_id:
            home_corners, away_corners = extract_corners(
                fx.get("statistics") or [], home_p_id, away_p_id
            )

        # Write score to fixtures
        conn.execute("""
            UPDATE fixtures SET
                home_score=?, away_score=?, total_goals=?,
                status='settled', updated_at=?
            WHERE id=?
        """, (home_score, away_score, total_goals, now_ts, db_row["id"]))
        updated += 1

        print(f"    OK {db_row['home_team_name']} {home_score}-{away_score} {db_row['away_team_name']}"
              f"  corners={home_corners}/{away_corners}")

        # Write fixture_stats if corners available
        if home_corners is not None and away_corners is not None:
            conn.execute("""
                INSERT OR REPLACE INTO fixture_stats
                    (fixture_id, home_corners, away_corners, total_corners)
                VALUES (?, ?, ?, ?)
            """, (db_row["id"], home_corners, away_corners, home_corners + away_corners))
            inserted_stats += 1

    time.sleep(0.5)

conn.execute(
    "INSERT INTO system_health (metric, value) VALUES (?, ?)",
    ("fetch_results", f"ok: {updated} scores, {inserted_stats} stats"),
)
conn.commit()
conn.close()

print()
print(f"Done")
print(f"  Scores written:        {updated}")
print(f"  Corner stats written:  {inserted_stats}")
print(f"  No score yet:          {skipped_no_score}")
print()
if updated > 0:
    print("Next step: run  python settle.py  to write pick_results from emit_log.")
