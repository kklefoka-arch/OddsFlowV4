"""V3.1 — Corner-stats backfill for settled fixtures missing fixture_stats.

Targets settled fixtures (home_score IS NOT NULL) in the last 14 days that
don't have a fixture_stats row yet (Sportmonks may publish corner data with
a delay or only on subsequent fetches). Re-queries the same fixtures/between
endpoint used by fetch_results.py and updates fixture_stats if corners arrive.

Run nightly after fetch_results so any picks that settled today but had no
corners yet can be re-attempted by settle.py on the next pass.
"""
import os
import sqlite3
import urllib.request
import urllib.parse
import json
import time
from collections import defaultdict
from datetime import date as date_cls, datetime, timedelta, timezone

TOKEN = os.environ.get(
    "SPORTMONKS_TOKEN",
    "2AWINN4fYPiQkY2lfHee9TASZubv74uP1RIY4ILY15Mzg4bw5bH2v2SeKGAN",
)
DB    = r"C:\OddsFlowV4\data\oddsflow_v4.db"
BASE  = "https://api.sportmonks.com/v3/football"

CORNERS_TYPE_ID = 34
LOOKBACK_DAYS = 14  # base window; adaptive cap below
LOOKBACK_MAX_DAYS = 60  # Bundle 6: don't reach further than this even with stranded picks


def api_get(path: str, params: dict, retries: int = 3) -> dict:
    params["api_token"] = TOKEN
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(8 * (2 ** attempt))
    raise last_err  # type: ignore[misc]


def fetch_all(path: str, params: dict, max_pages: int = 20):
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
        time.sleep(0.25)
    return rows


def extract_corners(stats_list, home_p_id, away_p_id):
    h = a = None
    for s in (stats_list or []):
        if s.get("type_id") != CORNERS_TYPE_ID:
            continue
        val = (s.get("data") or {}).get("value")
        if val is None: continue
        try: val = int(val)
        except (TypeError, ValueError): continue
        pid = s.get("participant_id")
        if pid == home_p_id: h = val
        elif pid == away_p_id: a = val
    return h, a


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_utc = datetime.now(timezone.utc)
now_ts  = now_utc.strftime("%Y-%m-%d %H:%M:%S")

# Bundle 6 (Session 23d) — adaptive lookback. If a corners_nl pick is sitting
# unsettled because the fixture has no fixture_stats row, stretch the window
# to cover it. Stops corners published late by Sportmonks from being stranded
# by the old hard 14-day cap. Capped at LOOKBACK_MAX_DAYS so the script
# doesn't scan the whole DB every night.
adaptive_row = conn.execute("""
    SELECT MIN(f.date) AS oldest
    FROM emit_log em
    JOIN fixtures f ON f.id = em.fixture_id
    LEFT JOIN pick_results pr ON pr.pick_uuid = em.pick_uuid
    LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
    WHERE em.market = 'corners_nl'
      AND pr.pick_uuid IS NULL
      AND f.home_score IS NOT NULL
      AND fs.fixture_id IS NULL
""").fetchone()
adaptive_oldest = adaptive_row["oldest"] if adaptive_row else None
adaptive_days = LOOKBACK_DAYS
if adaptive_oldest:
    try:
        oldest_dt = datetime.fromisoformat(adaptive_oldest.replace(" ", "T"))
        if oldest_dt.tzinfo is None:
            oldest_dt = oldest_dt.replace(tzinfo=timezone.utc)
        adaptive_days = min(
            LOOKBACK_MAX_DAYS,
            max(LOOKBACK_DAYS, int((now_utc - oldest_dt).days) + 1),
        )
    except Exception:
        adaptive_days = LOOKBACK_DAYS
cutoff  = (now_utc - timedelta(days=adaptive_days)).strftime("%Y-%m-%d")
print(f"Adaptive lookback: {adaptive_days}d (base {LOOKBACK_DAYS}, cap {LOOKBACK_MAX_DAYS})")

# Settled fixtures with no fixture_stats row, in lookback window.
missing = conn.execute("""
    SELECT f.id, f.sportmonks_id, f.date, f.home_team_name, f.away_team_name
    FROM fixtures f
    LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
    WHERE f.home_score IS NOT NULL
      AND f.sportmonks_id IS NOT NULL
      AND fs.fixture_id IS NULL
      AND substr(f.date, 1, 10) >= ?
    ORDER BY f.date DESC
""", (cutoff,)).fetchall()

print(f"Settled fixtures missing corner stats (last {adaptive_days}d): {len(missing)}")
if not missing:
    conn.execute(
        "INSERT INTO system_health (metric, value) VALUES (?, ?)",
        ("refresh_stats", f"ok: 0 missing ts={now_ts}"),
    )
    conn.commit()
    conn.close()
    raise SystemExit(0)

sm_map = {int(r["sportmonks_id"]): r for r in missing}

# Group by week to minimise API calls (matches fetch_results.py pattern).
by_week = defaultdict(list)
for r in missing:
    d = date_cls.fromisoformat((r["date"] or "")[:10])
    monday = d - timedelta(days=d.weekday())
    by_week[monday.isoformat()].append(r)

print(f"Grouped into {len(by_week)} week window(s)\n")

filled = 0
still_missing = 0
errors = 0
for week_start in sorted(by_week):
    week_rows = by_week[week_start]
    week_end  = (date_cls.fromisoformat(week_start) + timedelta(days=6)).isoformat()
    try:
        batch = fetch_all(
            f"fixtures/between/{week_start}/{week_end}",
            {"include": "statistics;participants"},
        )
    except Exception as e:
        print(f"  API error on {week_start}: {e}")
        errors += len(week_rows)
        continue

    targets = {int(r["sportmonks_id"]) for r in week_rows}
    for fx in batch:
        sm = fx.get("id")
        if sm is None or int(sm) not in targets:
            continue
        db_row = sm_map[int(sm)]

        parts = fx.get("participants") or []
        h_pid = next(
            (int(p["id"]) for p in parts if p.get("meta", {}).get("location") == "home"),
            None,
        )
        a_pid = next(
            (int(p["id"]) for p in parts if p.get("meta", {}).get("location") == "away"),
            None,
        )
        if not (h_pid and a_pid):
            still_missing += 1
            continue
        hc, ac = extract_corners(fx.get("statistics") or [], h_pid, a_pid)
        if hc is None or ac is None:
            still_missing += 1
            continue
        conn.execute("""
            INSERT OR REPLACE INTO fixture_stats
              (fixture_id, home_corners, away_corners, total_corners, raw_stats_json)
            VALUES (?, ?, ?, ?, ?)
        """, (db_row["id"], hc, ac, hc + ac, json.dumps(fx.get("statistics") or [])))
        filled += 1
        print(f"    OK {db_row['home_team_name']} vs {db_row['away_team_name']}  "
              f"corners={hc}+{ac}")
    time.sleep(0.5)

conn.execute(
    "INSERT INTO system_health (metric, value) VALUES (?, ?)",
    ("refresh_stats",
     f"ok: filled={filled} still_missing={still_missing} errors={errors} ts={now_ts}"),
)
conn.commit()
conn.close()

print()
print(f"Done — corners filled: {filled}")
print(f"       still missing:  {still_missing}  (Sportmonks didn't return stats)")
print(f"       API errors:     {errors}")
