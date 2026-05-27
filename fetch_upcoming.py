"""Fetch upcoming fixtures + pre-match odds from Sportmonks.

Uses the date-range endpoint which is the correct V3 API approach.
Filters to only the 3 currently active leagues: PL (8), MLS (779), Ireland (360).
"""
import sqlite3, urllib.request, urllib.parse, json, time
from datetime import datetime, timezone

TOKEN  = "2AWINN4fYPiQkY2lfHee9TASZubv74uP1RIY4ILY15Mzg4bw5bH2v2SeKGAN"
DB     = r"C:\OddsFlowV4\data\oddsflow_v4.db"

TODAY     = datetime.now(timezone.utc).strftime("%Y-%m-%d")
END_DATE  = "2026-12-31"

# All 30 subscribed leagues — sportmonks_id: tier
ACTIVE_LEAGUES = {
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

BASE = "https://api.sportmonks.com/v3/football"


def api_get(path: str, params: dict, retries: int = 3) -> dict:
    params["api_token"] = TOKEN
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                wait = 8 * (2 ** attempt)
                print(f"  [retry {attempt + 1}/{retries - 1}] {e} — sleeping {wait}s")
                time.sleep(wait)
    raise last_err  # type: ignore[misc]


def fetch_all(path: str, params: dict, max_pages: int = 30) -> list:
    rows, page = [], 1
    while page <= max_pages:
        p = {**params, "page": page, "per_page": 25}
        data = api_get(path, p)
        batch = data.get("data", [])
        if not isinstance(batch, list):
            break
        rows.extend(batch)
        print(f"  page {page}: {len(batch)} rows (total so far: {len(rows)})")
        if not data.get("pagination", {}).get("has_more"):
            break
        page += 1
        time.sleep(0.5)
    return rows


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
            if label in ("home", "1"):      home_odd = val
            elif label in ("draw", "x"):    draw_odd = val
            elif label in ("away", "2"):    away_odd = val
        elif mid == 14:
            if label == "yes":   btts_yes = val
            elif label == "no":  btts_no  = val
        elif mid == 7 and label == "over":
            try:
                line = float(o.get("total") or "")
            except (TypeError, ValueError):
                continue
            if line in goals_buckets:
                goals_buckets[line].append(val)
        elif mid == 45 and label == "over":
            # Corners total — market_id 45 in Sportmonks v3
            try:
                line = float(o.get("total") or "")
            except (TypeError, ValueError):
                continue
            if line in corners_buckets:
                corners_buckets[line].append(val)
    g15  = max(goals_buckets[1.5])   if goals_buckets[1.5]   else None
    g25  = max(goals_buckets[2.5])   if goals_buckets[2.5]   else None
    g35  = max(goals_buckets[3.5])   if goals_buckets[3.5]   else None
    c75  = max(corners_buckets[7.5]) if corners_buckets[7.5] else None
    c85  = max(corners_buckets[8.5]) if corners_buckets[8.5] else None
    c95  = max(corners_buckets[9.5]) if corners_buckets[9.5] else None
    return home_odd, draw_odd, away_odd, btts_yes, btts_no, g15, g25, g35, c75, c85, c95


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
now_ts = datetime.now(timezone.utc).isoformat()

# Build set of known team sportmonks_ids
teams_seen = {
    r["sportmonks_id"]
    for r in conn.execute(
        "SELECT sportmonks_id FROM teams WHERE sportmonks_id IS NOT NULL"
    ).fetchall()
}

# Build sportmonks_id → internal leagues.id map so fixtures store the correct FK
_league_id_map: dict[int, int] = {
    r["sportmonks_id"]: r["id"]
    for r in conn.execute(
        "SELECT id, sportmonks_id FROM leagues WHERE sportmonks_id IS NOT NULL"
    ).fetchall()
}

inserted = updated = skipped = 0

# Fetch in monthly windows — keeps each batch small and avoids timeouts.
# The leagueIds filter is silently ignored on this endpoint, so we filter
# by league in Python after fetch.
# First window starts from TODAY (not a hardcoded date) to avoid re-fetching
# already-played fixtures on every run.
# July–Oct windows use monthly splits (max_pages=30) to avoid hitting the
# 20-page / 1,000-fixture cap for dense periods.
windows = [
    (TODAY,        "2026-06-15", 20),
    ("2026-06-16", "2026-06-30", 20),
    ("2026-07-01", "2026-07-31", 30),
    ("2026-08-01", "2026-08-31", 30),
    ("2026-09-01", "2026-09-30", 30),
    ("2026-10-01", "2026-10-31", 30),
    ("2026-11-01", "2026-12-31", 20),
]

all_fixtures: list = []
for start, end, max_pg in windows:
    print(f"\nWindow {start} to {end}")
    batch = fetch_all(
        f"fixtures/between/{start}/{end}",
        {"include": "participants;odds"},
        max_pages=max_pg,
    )
    # Filter to active leagues only
    relevant = [fx for fx in batch if fx.get("league_id") in ACTIVE_LEAGUES]
    print(f"  {len(batch)} total, {len(relevant)} in active leagues")
    all_fixtures.extend(relevant)

fixtures = all_fixtures
print(f"\nTotal relevant fixtures: {len(fixtures)}")

for fx in fixtures:
    sm_id     = fx["id"]
    raw_start = fx.get("starting_at") or ""
    kickoff_utc = raw_start.replace("T", " ").split(".")[0]  # "2026-05-23 21:00:00"
    fx_date   = kickoff_utc[:10]  # date-only for skip comparison
    league_id = fx.get("league_id")
    tier      = ACTIVE_LEAGUES.get(league_id)

    if not tier or fx_date < TODAY:
        skipped += 1
        continue

    # Resolve internal DB league id (fallback: sportmonks id, works for legacy rows)
    internal_league_id = _league_id_map.get(league_id, league_id)

    participants = fx.get("participants", [])
    home_team = next((p for p in participants if p.get("meta", {}).get("location") == "home"), None)
    away_team = next((p for p in participants if p.get("meta", {}).get("location") == "away"), None)
    if not home_team or not away_team:
        skipped += 1
        continue

    for team in (home_team, away_team):
        tsm = team["id"]
        if tsm not in teams_seen:
            conn.execute(
                "INSERT OR IGNORE INTO teams (name, sportmonks_id) VALUES (?, ?)",
                (team.get("name", f"Team {tsm}"), tsm),
            )
            teams_seen.add(tsm)

    ht = conn.execute("SELECT id FROM teams WHERE sportmonks_id=?", (home_team["id"],)).fetchone()
    at = conn.execute("SELECT id FROM teams WHERE sportmonks_id=?", (away_team["id"],)).fetchone()
    if not ht or not at:
        skipped += 1
        continue

    home_odd, draw_odd, away_odd, btts_yes, btts_no, g15, g25, g35, c75, c85, c95 = extract_odds(fx.get("odds", []))

    # Classify zone + bts_pocket inline for storage
    def _zone(d):
        if d is None: return None
        if d < 2.70: return None
        if d < 3.40: return "strong"
        if d < 4.10: return "standard"
        if d < 4.80: return "low"
        return "one_sided"

    def _bts(y, n):
        if y is None or n is None: return None
        return ("strong_over" if y < 1.50 else "slight_over") if y <= n \
            else ("strong_under" if n < 1.50 else "slight_under")

    fx_zone = _zone(draw_odd)
    fx_bts  = _bts(btts_yes, btts_no)

    existing = conn.execute(
        "SELECT id FROM fixtures WHERE sportmonks_id=?", (sm_id,)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE fixtures SET
                league_id=?, date=?, home_odd=?, draw_odd=?, away_odd=?,
                btts_yes_odd=?, btts_no_odd=?,
                goals_over_15_odd=?, goals_over_25_odd=?, goals_over_35_odd=?,
                corners_over_75_odd=?, corners_over_85_odd=?, corners_over_95_odd=?,
                draw_zone=?, bts_pocket=?, updated_at=?
            WHERE sportmonks_id=?
        """, (internal_league_id, kickoff_utc, home_odd, draw_odd, away_odd,
              btts_yes, btts_no, g15, g25, g35, c75, c85, c95,
              fx_zone, fx_bts, now_ts, sm_id))
        updated += 1
    else:
        conn.execute("""
            INSERT INTO fixtures
                (sportmonks_id, league_id, tier, date, status,
                 home_team_id, away_team_id, home_team_name, away_team_name,
                 home_odd, draw_odd, away_odd, btts_yes_odd, btts_no_odd,
                 goals_over_15_odd, goals_over_25_odd, goals_over_35_odd,
                 corners_over_75_odd, corners_over_85_odd, corners_over_95_odd,
                 draw_zone, bts_pocket, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            sm_id, internal_league_id, tier, kickoff_utc, "scheduled",
            ht["id"], at["id"],
            home_team.get("name"), away_team.get("name"),
            home_odd, draw_odd, away_odd, btts_yes, btts_no,
            g15, g25, g35, c75, c85, c95,
            fx_zone, fx_bts, now_ts, now_ts,
        ))
        inserted += 1

conn.execute(
    "INSERT INTO system_health (metric, value) VALUES ('fetch_upcoming', 'ok')",
)
conn.commit()
conn.close()
print(f"\nDone — inserted={inserted}  updated={updated}  skipped={skipped}")
