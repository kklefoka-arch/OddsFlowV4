# OddsFlow V4 — Fixture Lifecycle Process Flow

Every phase a fixture moves through from API fetch to historical data.
Every function, table, field, and feedback loop documented exactly as it exists.
Gaps are labelled **[GAP]** — things the system needs but does not have yet.

---

## Overview

```
[Sportmonks API]
       |
  Phase 1: FETCH
       |
  Phase 2: LAND
       |
  Phase 3: CLASSIFY  <────────────────────────────┐
       |                                           │
  Phase 4: CALIBRATE ← (settled fixtures feed in) │
       |                                           │
  Phase 5: EMIT                                    │
       |                                           │
  Phase 6: DISPLAY                                 │
       |                                           │
  Phase 7: OBSERVE (pre-match)                     │
       |                                           │
  [Match is played — external event]               │
       |                                           │
  Phase 8: SCORE UPDATE  ← [GAP]                   │
       |                                           │
  Phase 9: SETTLE                                  │
       |                                           │
  Phase 10: REPORT                                 │
       |                                           │
  Phase 11: RECALIBRATE ──────────────────────────>┘
       |
  Phase 12: VALIDATE (drift — baseline vs recent)
       |
  [Fixture is historical data — feeds Phase 4 forever]
```

---

## Phase 1: FETCH

**What**: Pull upcoming fixtures and pre-match odds from Sportmonks API.

**Script**: `fetch_upcoming.py`

**Trigger**: Manual — run daily by operator.

**API endpoint called**: `GET /v3/football/fixtures/between/{start}/{end}?include=participants;odds`

**Fetch windows** (current):
| Window | Start | End |
|--------|-------|-----|
| 1 | 2026-05-22 | 2026-06-30 |
| 2 | 2026-07-01 | 2026-08-31 |
| 3 | 2026-09-01 | 2026-10-31 |
| 4 | 2026-11-01 | 2026-12-31 |

**League filter**: `ACTIVE_LEAGUES` dict — 30 leagues mapped `sportmonks_id → tier`. Fixtures from other leagues are discarded.

**Known issue**: `leagueIds` filter is silently ignored by this Sportmonks endpoint. Filtering happens in Python after fetch.

**Odds extracted** (from `extract_odds()`):
| Field | Market ID | Label |
|-------|-----------|-------|
| `home_odd` | 1 | "home" / "1" |
| `draw_odd` | 1 | "draw" / "x" |
| `away_odd` | 1 | "away" / "2" |
| `btts_yes_odd` | 14 | "yes" |
| `btts_no_odd` | 14 | "no" |

**Kickoff datetime**:
```python
raw = fx.get("starting_at") or ""          # e.g. "2026-05-23T21:00:00.000000Z"
kickoff_utc = raw.replace("T", " ").split(".")[0]  # "2026-05-23 21:00:00"
```

**Skip conditions**:
- `league_id` not in `ACTIVE_LEAGUES`
- `kickoff_utc[:10]` < TODAY (past fixtures)
- Missing home or away participant

**Output**: Rows ready to insert or update in `fixtures` table.

---

## Phase 2: LAND

**What**: Store or update the fixture in the database.

**Table written**: `fixtures`

**Logic** (idempotent):
- If `sportmonks_id` already exists → `UPDATE` odds + kickoff datetime
- If not → `INSERT` new row

**Fields written on INSERT**:
```
sportmonks_id, league_id (internal FK via _league_id_map),
tier, date (kickoff_utc), status="scheduled",
home_team_id, away_team_id, home_team_name, away_team_name,
home_odd, draw_odd, away_odd, btts_yes_odd, btts_no_odd,
created_at, updated_at
```

**Fields written on UPDATE**:
```
league_id, date (kickoff_utc), home_odd, draw_odd, away_odd,
btts_yes_odd, btts_no_odd, updated_at
```

**Teams**: Auto-inserted into `teams` if not already known (by `sportmonks_id`).

**League resolution**: `_league_id_map` = `{sportmonks_id: internal_db_id}`. This resolves Sportmonks league IDs to the internal `leagues.id` FK.

**Schema fields NOT written here** (exist in schema, currently unused):
- `draw_zone`, `bts_pocket` — schema says "computed on insert" but no code populates them
- `goals_over_15_odd`, `corners_over_85_odd` — not extracted from Sportmonks
- `home_score`, `away_score`, `total_goals` — populated at Phase 8 [GAP]

**Known gap**: 1,349 historical fixtures have `sportmonks_id = NULL` and `date` as date-only (`"2026-05-23"`). These were seeded by the V2/V3 historical pipeline which stored the Sportmonks ID as the row `id` (primary key) rather than `sportmonks_id`. The fetch UPDATE cannot match them (`WHERE sportmonks_id = ?`). They have no odds and are invisible to all downstream phases.

---

## Phase 3: CLASSIFY

**What**: Assign a fixture to a (draw_zone × bts_pocket) cell from its odds.

**When**: On-demand. Called wherever fixtures are displayed or processed. NOT stored.

**Function**: `classify_fixture(row)` in `app/engine/classify.py`

**Returns**: `{zone, bts_pocket, tier}`

### Draw Zone — `zone_of(draw_odd)`

| Zone | Condition | Meaning |
|------|-----------|---------|
| `None` (excluded) | `draw_odd < 2.70` or `None` | Heavy favourite — too one-sided for draw analysis |
| `strong` | `2.70 ≤ draw_odd < 3.40` | Competitive match, draw likely |
| `standard` | `3.40 ≤ draw_odd < 4.10` | Moderate draw likelihood |
| `low` | `4.10 ≤ draw_odd < 4.80` | Draw unlikely — MEASURING (data accumulating) |
| `one_sided` | `draw_odd ≥ 4.80` | Strong favourite — Alpha Win market |

### BTS Pocket — `bts_of(btts_yes_odd, btts_no_odd)`

The "BTS pocket" describes the BTTS market sentiment. "Yes favoured" = `yes_odd ≤ no_odd`.

| Pocket | Condition | Meaning |
|--------|-----------|---------|
| `strong_over` | yes favoured AND `yes_odd < 1.50` | Strong expectation both teams score |
| `slight_over` | yes favoured AND `yes_odd ≥ 1.50` | Slight lean toward both teams scoring |
| `slight_under` | no favoured AND `no_odd ≥ 1.50` | Slight lean toward clean sheet |
| `strong_under` | no favoured AND `no_odd < 1.50` | Strong expectation of a clean sheet |
| `None` | Either odd is `None` | Unclassifiable |

**Cell**: The combination `(zone, bts_pocket)` defines a cell in the foundation matrix. There are 4 zones × 4 pockets = 16 possible cells (minus any with insufficient data).

---

## Phase 4: CALIBRATE

**What**: Compute the Foundation Matrix — historical hit rates and promotion status for each cell.

**When**: On every API call to `/api/foundation` or `/picks`. Always computed fresh — not cached.

**Step 1 — Load**: `load_foundation(conn)` in `app/engine/foundation.py`

Queries all settled fixtures with complete odds:
```sql
SELECT f.draw_odd, f.btts_yes_odd, f.btts_no_odd,
       f.home_odd, f.away_odd,
       f.home_score, f.away_score,
       f.tier,
       fs.home_corners, fs.away_corners
FROM fixtures f
LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
WHERE f.home_score IS NOT NULL AND f.away_score IS NOT NULL
  AND f.draw_odd IS NOT NULL AND f.btts_yes_odd IS NOT NULL
  AND f.btts_no_odd IS NOT NULL AND f.home_odd IS NOT NULL
  AND f.away_odd IS NOT NULL
```

Returns: **28,477 rows** (as of 2026-05-23).

**Step 2 — Compute**: `compute_foundation(rows)` in `app/engine/promotion.py`

For each row: classify zone + bts_pocket, then accumulate into cell accumulators.

**Per cell, hit rates computed**:
| Field | What it measures |
|-------|-----------------|
| `gn_hit` | Goals natural hit: total goals > natural line |
| `gs_hit` | Goals system hit: total goals > system line (1-up) |
| `cn_hit` | Corners natural hit: total corners > natural line |
| `cs_hit` | Corners system hit: total corners > system line |
| `threeway_hit` | DNB/Alpha Win pick hit: alpha wins or draws (strong/standard) / alpha wins outright (one_sided) |

### Natural Lines — `natural_lines.py`

Lines are zone-dependent. Each zone has a natural line and a system line (1-up from natural):

| Zone | Goals Natural | Goals System | Corners Natural | Corners System |
|------|--------------|-------------|----------------|---------------|
| `strong` | 1.5 | 2.5 | 7.5 | 8.5 |
| `standard` | 1.5 | 2.5 | 7.5 | 8.5 |
| `low` | 2.5 | 3.5 | 8.5 | 9.5 |
| `one_sided` | 2.5 | 3.5 | 8.5 | 9.5 |

"Natural line" = the market's expected total for that type of fixture. "System line" = 1 step higher — the stricter test.

**Drop** = `natural_hit - system_hit`. High drop means performance is fragile: the market is barely clearing the natural line and fails badly at the system line.

**Step 3 — Promote**: `_assign_ranks_and_promotion()`

Within each zone, cells are ranked by drop (ascending: rank 1 = lowest/best drop).

**Promotion thresholds** (`PROMOTE_THRESHOLD = 72.0`, `PROMOTE_LOWER = 67.5`):

| Status | Condition | Meaning |
|--------|-----------|---------|
| `PROMOTE` | hit ≥ 72.0% | Promoted — use this cell |
| `PROMOTE_TOLERANCE` | 67.5% ≤ hit < 72.0% AND drop rank qualifies | Promoted with tolerance |
| `HOLD` | 67.5% ≤ hit < 72.0% AND drop rank fails | Too fragile — hold |
| `NO` | hit < 67.5% | Not promoted |
| `MEASURING` | PROMOTE/PROMOTE_TOLERANCE but zone = `low` | Suppressed — accumulating data |

**Drop rank qualification for PROMOTE_TOLERANCE**: rank 1, OR drop ≤ rank-1 drop + 4.5pp.

**Applied to three markets**: goals_promote, corners_promote, threeway_promote. In V4, only `threeway_promote` drives picks.

**`cell_promoted`**: True if ANY of the three market statuses is PROMOTE or PROMOTE_TOLERANCE. Used for display. NOT the same as "this cell generates picks" — picks use `threeway_promote` only.

**Tier splits**: Foundation computed three times — `all` (all fixtures), `t1` (tier=1 only), `t2t3` (tier=2 or 3).

**Output** (`/api/foundation`):
```
{
  all:     [15 cells],
  t1:      [15 cells],
  t2t3:    [15 cells],
  summary: {total_fixtures: 28477, promoted_cells: 10, last_updated: ...}
}
```

`promoted_cells` = cells in `all` tier where `threeway_promote in (PROMOTE, PROMOTE_TOLERANCE)` AND `zone != "low"`.

---

## Phase 5: EMIT

**What**: For each upcoming promoted fixture in the window, generate a pick and write it to `emit_log`.

**Route**: `GET /picks` — `app/api/routes_picks.py`

**Window**: default `days=3`. Queries: `home_score IS NULL AND date >= today AND substr(date,1,10) <= horizon`.

**Step 1 — Build promoted set**: Re-runs Phase 4 (load + compute) fresh on every call. Promoted set = cells where `threeway_promote in (PROMOTE, PROMOTE_TOLERANCE)` and `zone != "low"`.

**Step 2 — Fetch upcoming fixtures** in window (with odds + team names + league).

**Step 3 — Per fixture**:

1. `classify_fixture()` → zone + bts_pocket
2. Check if (zone, bts_pocket) in promoted set → if not, skip
3. Assign market: `_ZONE_MARKET = {strong: dnb, standard: dnb, one_sided: alpha_win}`
4. Identify alpha team: `_alpha_is_home()` — team with lower (more favoured) 1X2 odd. `home_odd ≤ away_odd` → home is alpha.
5. Derive pick odd:
   - DNB: `(1 - p_draw) / p_alpha` where `p = 1/odd`
   - Alpha Win: `min(home_odd, away_odd)`
6. Compute drift: `_compute_cell_drift()` — compare recent emit_log outcomes vs historical baseline. Returns flag + gap.
7. Build pick output row.

**Step 4 — Write emit_log**: `write_emit_log()` — idempotent via `INSERT OR IGNORE` on `pick_uuid`.

**`pick_uuid`**: `SHA256("{fixture_id}:{market}:{pick}")[:36]`

This means: same fixture + market + pick always produces the same UUID. Running `/picks` multiple times writes the row once, skips on repeat.

**emit_log fields written**:
```
pick_uuid, emitted_at, fixture_id, zone, bts_pocket, tier,
market, pick, pick_odd, confidence (= threeway_hit / 100)
```

**Skip reasons tracked**:
- `unclassifiable`: zone=None or bts=None (missing odds, or excluded draw zone)
- `partition_not_promoted`: cell not in promoted set, or zone not in `_ZONE_MARKET`

**Current state (2026-05-23)**: 207 emit_log entries, all PENDING.

---

## Phase 6: DISPLAY

**What**: The SPA Picks tab shows the current window's picks to the operator.

**SPA tab**: Picks (default tab, loads on page open)

**JS function**: `loadPicks()` → `fetch('/picks')` → renders pick cards

**Each pick card shows**:
- Fixture: home team vs away team, league, kickoff time
- Market: DNB or Alpha Win
- Pick: alpha team name
- Pick odd (derived)
- Cell: zone + BTS pocket
- Historical hit rate
- Drift flag (stable / watch / drifting / no_data)

**Kickoff display**: `parseKickoffUtc("2026-05-23 21:00:00")` → local time display

**Parallel display**: Inspector partition_drift tab shows per-cell drift for all promoted cells (not just current picks).

---

## Phase 7: OBSERVE (Pre-Match)

**What**: Operator monitors upcoming fixtures and engine calibration before kick-off.

### Upcoming Tab
**Route**: `GET /upcoming` — `app/api/routes_upcoming.py`

Shows every upcoming fixture in the 7-day window with:
- Classification (zone, bts_pocket) computed live
- `partition_promoted` flag: True if (zone, bts_pocket) is in the live promoted set
- No picks emitted here — observation only

### Inspector — Partition Drift
**Route**: `GET /inspector/partition_drift`

Per promoted cell:
- Historical hit rate (from foundation matrix baseline)
- Recent hit rate (from settled emit_log rows in last N days)
- Gap (pp) = recent - historical
- Flag: `stable`, `watch` (≤-5pp), `drifting` (≤-10pp), `no_data` (<10 settled emits)

**Drift uses**: All settled emit_log entries (where fixture has home_score IS NOT NULL). Currently 0 rows qualify (no emitted fixtures have settled yet).

### Inspector — Similar Odds / Pre-Match Lens
**[GAP]**: No endpoint currently returns a "similar fixtures" or "pre-match odds lens" view. The inspector only has drift, recent_settled, and daily_calendar. Similar-odds history would require querying historical fixtures by draw_odd range + bts_pocket.

---

## Phase 8: SCORE UPDATE

**What**: Fixture is played. Scores become available. Our DB must be updated with `home_score`, `away_score`.

**[GAP — CRITICAL]**: There is no automated score update pipeline. `fetch_upcoming.py` only updates odds for upcoming fixtures (`home_score IS NULL`). It does not fetch or write scores.

**How the 28,477 existing settled fixtures got their scores**: These came from the V2/V3 historical ingestion pipeline (now removed). They were seeded with scores already.

**What this means going forward**: Fixtures fetched by the current `fetch_upcoming.py` will NEVER have their scores written unless a score-fetch pipeline is built. Without scores, Phase 9 (settle) cannot run, Phase 10 (reports) has no data, and Phase 11 (recalibrate) never grows.

**Required but not yet built**: A `fetch_results.py` script that:
1. Queries fixtures where `date < now AND home_score IS NULL`
2. Calls Sportmonks results endpoint for those fixture IDs
3. Writes `home_score`, `away_score`, `total_goals` to `fixtures`
4. Writes corner stats to `fixture_stats`
5. Updates `status = 'settled'`

---

## Phase 9: SETTLE

**What**: Match emit_log entries to fixture results. Write outcome to `pick_results`.

**Script**: `settle.py`

**Trigger**: Manual — run after matches complete.

**Logic**:
1. Query emit_log entries where fixture has `home_score IS NOT NULL` and no existing `pick_results` row.
2. `settle_pick(market, home_score, away_score, home_odd, away_odd)`:
   - Identify alpha team: `home_odd ≤ away_odd` → alpha is home
   - Alpha wins: `home_score > away_score` (if alpha home) or `away_score > home_score`
   - Draw: `home_score == away_score`
   - **DNB**: WIN (alpha wins) | VOID (draw) | LOSS (alpha loses)
   - **Alpha Win**: WIN (alpha wins) | LOSS (draw or alpha loses)
3. Write to `pick_results`: `pick_uuid, settled_at, outcome (WIN/VOID/LOSS), actual_value (1.0/0.5/0.0)`.

**Idempotent**: `INSERT OR IGNORE` — safe to run multiple times.

**Tables written**: `pick_results`

**Current state**: 0 rows in `pick_results`. Will populate once Phase 8 is working (scores written).

---

## Phase 10: REPORT

**What**: Operator reviews pick performance post-match.

### On-the-fly settlement (does NOT require settle.py to have run)

**Route**: `GET /reports/emit_performance`
- Pulls emit_log + fixture scores
- Runs `settle_pick()` in memory per row
- Returns per-window stats (1d, 3d, 7d, 30d, 90d, 180d)
- Works as long as fixture has a score — does NOT need `pick_results`

**Route**: `GET /reports/emit_recent`
- Per-fixture readback of recent emits with live outcome
- Does NOT need `pick_results`

### pick_results-dependent (REQUIRES settle.py to have run)

**Route**: `GET /inspector/recent_settled`
- Reads from `pick_results` JOIN `emit_log` JOIN `fixtures`
- Returns settled picks grouped by fixture
- Currently returns 0 fixtures (no `pick_results` rows)

**Route**: `GET /inspector/daily_calendar`
- Reads from `pick_results`
- Returns per-day WIN/VOID/LOSS counts for calendar view
- Currently returns empty calendar (no `pick_results` rows)

**Route**: `GET /reports/settle_activity`
- Reads from `pick_results` + `system_health`
- Currently returns empty

**Route**: `GET /reports/emit_market_breakdown`
- On-the-fly settlement per (zone, bts, market, pick) bucket
- Does NOT need `pick_results`

---

## Phase 11: RECALIBRATE

**What**: The newly settled fixture automatically becomes part of the Foundation Matrix for all future calibrations.

**How**: No explicit action needed. `load_foundation(conn)` queries `WHERE home_score IS NOT NULL`. The moment a fixture gets its score written (Phase 8), it is included in the next call to `/api/foundation` or `/picks`.

**Effect**: Foundation cell hit rates shift. Promotion status may change. A cell near the threshold might cross from PROMOTE_TOLERANCE → PROMOTE, or drift from PROMOTE → HOLD.

**Feedback loop**: Phase 11 → Phase 4. Every settled fixture tightens or adjusts the calibration.

---

## Phase 12: VALIDATE

**What**: Compare recent pick performance against the historical baseline to detect drift.

**Mechanism**: `_compute_cell_drift()` in `routes_picks.py` (also `compute_drift_rows()` in `routes_inspector.py`)

**Inputs**:
- Historical baseline: `cell["threeway_hit"]` from foundation matrix (Phase 4)
- Recent: emit_log rows for that cell in last N days where fixture has settled → `settle_pick()` → hit rate

**Gap = recent_hit - historical_hit** (in percentage points)

**Flags**:
| Flag | Condition |
|------|-----------|
| `stable` | gap > -5pp OR insufficient data resolved as stable |
| `watch` | -10pp < gap ≤ -5pp |
| `drifting` | gap ≤ -10pp |
| `no_data` | fewer than 10 settled emits in window |

**Where drift appears**:
- Per pick: `cell_drift_flag` in picks response (Picks tab)
- Per cell: `GET /inspector/partition_drift` (Inspector tab)

**Current state**: All cells show `no_data` — no emitted picks have settled yet (Phase 8 gap means no scores written for new fixtures).

---

## Where a Fixture "Leaves" the Active System

A fixture never literally leaves the database. What changes is its role:

| State | `home_score` | Role |
|-------|-------------|------|
| Upcoming | NULL | Candidate for pick emission; visible in Picks + Upcoming tabs |
| Settled | NOT NULL | Feeds foundation matrix calibration; visible in Reports + Inspector |

Once settled, a fixture moves permanently from "upcoming" to "historical." It feeds Phase 4 (calibration) indefinitely and is queried by reports and inspector routes.

---

## Connection Map

```
fetch_upcoming.py
  → fixtures table (writes: sportmonks_id, date, odds, team FKs)
  → teams table (auto-inserts unknown teams)

load_foundation(conn)
  ← fixtures table (reads: all settled rows with complete odds)
  ← fixture_stats table (reads: corners data)

compute_foundation(rows)
  → zone_of() + bts_of() [classify each row]
  → natural_line() + system_line() [compute drop]
  → _promote_status() / _threeway_promote_status() [assign status]
  → returns: {all, t1, t2t3, summary}

routes_picks.py
  ← load_foundation + compute_foundation [Phase 4 on demand]
  ← fixtures table [upcoming in window]
  → classify_fixture() [Phase 3]
  → _compute_cell_drift() [Phase 12]
  → write_emit_log() → emit_log table

settle.py
  ← emit_log table [pending settled picks]
  ← fixtures table [home_score, away_score, home_odd, away_odd]
  → pick_results table

routes_inspector.py
  ← pick_results table [recent_settled, daily_calendar]
  ← emit_log + fixtures [partition_drift]

routes_reports.py
  ← emit_log + fixtures [emit_performance, emit_recent, emit_market_breakdown]
  ← pick_results [settle_activity]
```

---

## Known Gaps

| # | Phase | Gap | Impact |
|---|-------|-----|--------|
| G1 | Phase 8 | No score/results fetch pipeline | Newly fetched fixtures never settle; foundation never grows from new data; pick_results stays empty |
| G2 | Phase 2 | `draw_zone` + `bts_pocket` in schema but never written | Schema misleads; classification is always on-the-fly |
| G3 | Phase 2 | 1,349 historical fixtures with `sportmonks_id=NULL` | Cannot be updated by fetch; inflate upcoming count; invisible to picks |
| G4 | Phase 7 | No "similar odds history" endpoint | Inspector pre-match lens incomplete |
| G5 | Phase 9 | settle.py manual only | Operator must remember to run it; no automation |
| G6 | All | No cron / scheduled automation | fetch + settle are manual daily tasks |
