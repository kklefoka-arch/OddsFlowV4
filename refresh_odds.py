"""V3.1 — Intraday odds refresh (M2 fix from Session 15 process audit).

Re-fetches 1X2 / BTTS / goals / corners odds for fixtures kicking off in the
NEXT 8 HOURS. Run mid-afternoon (14:30 SAST) so evening matches get fresh odds
before pick emission and operator review — the 08:00 fetch_upcoming odds drift
through the day as books absorb team news and money.

Does NOT insert new fixtures — only updates odds on fixtures already in the DB.

Pipeline order:
  fetch_upcoming (08:00) -> emit_picks (08:05) -> refresh_odds (14:30)
  -> fetch_results (23:30) -> settle (23:45)
"""
import os
import sqlite3
import urllib.request
import urllib.parse
import json
import time
from datetime import datetime, timedelta, timezone

TOKEN = os.environ.get(
    "SPORTMONKS_TOKEN",
    "2AWINN4fYPiQkY2lfHee9TASZubv74uP1RIY4ILY15Mzg4bw5bH2v2SeKGAN",
)
DB    = r"C:\OddsFlowV4\data\oddsflow_v4.db"
BASE  = "https://api.sportmonks.com/v3/football"
HORIZON_HOURS = 8


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


def extract_odds(odds_list: list):
    """Mirrors fetch_upcoming.extract_odds — same market IDs and labels."""
    home_odd = draw_odd = away_odd = btts_yes = btts_no = None
    g_buckets = {1.5: [], 2.5: [], 3.5: []}
    c_buckets = {7.5: [], 8.5: [], 9.5: []}
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
            if label == "yes":   btts_yes = val
            elif label == "no":  btts_no  = val
        elif mid == 7 and label == "over":
            try: line = float(o.get("total") or "")
            except (TypeError, ValueError): continue
            if line in g_buckets: g_buckets[line].append(val)
        elif mid == 45 and label == "over":
            try: line = float(o.get("total") or "")
            except (TypeError, ValueError): continue
            if line in c_buckets: c_buckets[line].append(val)
    return (
        home_odd, draw_odd, away_odd, btts_yes, btts_no,
        max(g_buckets[1.5]) if g_buckets[1.5] else None,
        max(g_buckets[2.5]) if g_buckets[2.5] else None,
        max(g_buckets[3.5]) if g_buckets[3.5] else None,
        max(c_buckets[8.5]) if c_buckets[8.5] else None,
    )


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_utc = datetime.now(timezone.utc)
horizon = now_utc + timedelta(hours=HORIZON_HOURS)
now_ts  = now_utc.strftime("%Y-%m-%d %H:%M:%S")

# Find upcoming fixtures kicking off within HORIZON_HOURS.
# Must have sportmonks_id (= already fetched by fetch_upcoming).
upcoming = conn.execute("""
    SELECT id, sportmonks_id, date, home_team_name, away_team_name
    FROM fixtures
    WHERE home_score IS NULL
      AND sportmonks_id IS NOT NULL
      AND date >= ? AND date <= ?
    ORDER BY date ASC
""", (now_ts, horizon.strftime("%Y-%m-%d %H:%M:%S"))).fetchall()

print(f"Fixtures kicking off in next {HORIZON_HOURS}h: {len(upcoming)}")
if not upcoming:
    conn.execute(
        "INSERT INTO system_health (metric, value) VALUES (?, ?)",
        ("refresh_odds", f"ok: 0 fixtures in window ts={now_ts}"),
    )
    conn.commit()
    conn.close()
    raise SystemExit(0)

sm_ids = [int(r["sportmonks_id"]) for r in upcoming]
sm_to_db = {int(r["sportmonks_id"]): r["id"] for r in upcoming}

# Batch by chunks of 50 sportmonks_ids (multi endpoint limit)
updated = 0
errors = 0
for i in range(0, len(sm_ids), 50):
    chunk = sm_ids[i:i + 50]
    csv = ",".join(str(x) for x in chunk)
    try:
        data = api_get(f"fixtures/multi/{csv}", {"include": "odds"})
    except Exception as e:
        print(f"  API error on chunk {i}: {e}")
        errors += len(chunk)
        continue
    items = data.get("data", []) or []
    for fx in items:
        sm = fx.get("id")
        db_id = sm_to_db.get(int(sm)) if sm is not None else None
        if db_id is None:
            continue
        (ho, do, ao, by, bn,
         g15, g25, g35, c85) = extract_odds(fx.get("odds") or [])
        conn.execute("""
            UPDATE fixtures SET
              home_odd       = COALESCE(?, home_odd),
              draw_odd       = COALESCE(?, draw_odd),
              away_odd       = COALESCE(?, away_odd),
              btts_yes_odd   = COALESCE(?, btts_yes_odd),
              btts_no_odd    = COALESCE(?, btts_no_odd),
              goals_over_15_odd  = COALESCE(?, goals_over_15_odd),
              goals_over_25_odd  = COALESCE(?, goals_over_25_odd),
              goals_over_35_odd  = COALESCE(?, goals_over_35_odd),
              corners_over_85_odd = COALESCE(?, corners_over_85_odd),
              updated_at = ?
            WHERE id = ?
        """, (ho, do, ao, by, bn, g15, g25, g35, c85, now_ts, db_id))
        if conn.total_changes > 0:
            updated += 1
    time.sleep(0.4)

conn.execute(
    "INSERT INTO system_health (metric, value) VALUES (?, ?)",
    ("refresh_odds",
     f"ok: refreshed {updated}/{len(upcoming)} (errors={errors}) ts={now_ts}"),
)
conn.commit()
conn.close()
print(f"Done — refreshed {updated}/{len(upcoming)}  errors={errors}")
