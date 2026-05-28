# OddsFlow V4 — System Language (V3.1)

Every term this system uses, defined exactly. When something is requested, reported, or questioned — this is the reference for what it means, where it lives, and what it connects to.

---

## Core Concepts

### Fixture
A single football match. Lives in the `fixtures` table.
- **Upcoming fixture:** `home_score IS NULL` — not yet played.
- **Settled fixture:** `home_score IS NOT NULL` — result in DB.
- **Classifiable fixture:** has `draw_odd`, `btts_yes_odd`, `btts_no_odd`, plus `home_odd` and `away_odd` for DF.

### Odds
Bookmaker prices on a fixture. V3.1 reads:

| Field | Market |
|-------|--------|
| `home_odd` / `draw_odd` / `away_odd` | 1X2 (Sportmonks market 1) |
| `btts_yes_odd` / `btts_no_odd` | BTTS (Sportmonks market 14) |
| `goals_over_15_odd` / `goals_over_25_odd` / `goals_over_35_odd` | Goal Line (market 7) |
| `corners_over_75_odd` / `corners_over_85_odd` / `corners_over_95_odd` | Corners totals |

The Over 1.5 goals and Over 8.5 corners prices are frequently NULL because bookmakers rarely quote trivial overs. This is expected.

### Alpha Team
The team with the lower 1X2 odd. `home_odd ≤ away_odd` → alpha is home. Used for DNB / alpha_win pick labels.

### Draw Zone
Fixture classification from `draw_odd`. See `zone_of()` in `app/engine/classify.py`.

### DF (Difference Factor)
Fixture classification from rounded `|home_odd − away_odd|`. DF0 (diff < 0.5) / DF1 (0.5 ≤ diff < 1.5) / DF2 (diff ≥ 1.5). See `df_of()`. V3.1 introduces DF as the third partition axis.

### BTS Pocket
Fixture classification from BTTS odds. See `bts_of()`.

### Cell
A `(zone, df, bts_pocket)` triple. 4 × 3 × 4 = 48 possible, 20 active in V3.1. Stored as partition key `zone:DF:bts_pocket` (e.g. `standard:DF1:slight_over`).

### Tier
League quality tier (1, 2, or 3). Stored in `fixtures.tier` and `leagues.tier`. Drives the T1 / T2+T3 / ALL Analysis-tab splits.

---

## Promotion Terms (V3.1)

### V3_ACTIVE
The authoritative pick policy. Dict keyed by `(zone, df, bts)` → market config. Imported by `routes_picks.py`. **This is what fires picks.** Source: `app/engine/static_policy.py`.

### V3_MARKETS
Full per-cell market definition: `line`, `hit` (historical), `n` (sample size), `odd_col` (column on `fixtures` to read the pick odd from). `V3_ACTIVE` is `V3_MARKETS` filtered by `LOW_ZONE_SUPPRESS`.

### PROMOTED_CELLS
Compatibility dict consumed by `routes_inspector.py` and `routes_reports.py`. Same 20 keys as `V3_ACTIVE` plus metadata (`threeway_hit`, `promote_status`).

### LOW_ZONE_SUPPRESS
Boolean flag. `False` in `static_policy.py` (low zone fires DNB picks). `True` in `promotion.py` (foundation matrix display marks low cells `MEASURING`). The split is intentional.

### Promote Status
String tag on a cell: `PASS`, `MARGINAL`, `FLAG`. Set at calibration time; surfaces in dashboards but does not gate picks.

### Compute Foundation
`compute_foundation(load_foundation(conn))` — computes the live foundation matrix from all settled fixtures. Used **for display only** (Analysis tab). Has its own PROMOTE / PROMOTE_TOLERANCE / HOLD / NO classification independent of V3.1.

---

## Pick Terms

### Pick
A market-specific recommendation generated for an upcoming fixture in a V3.1-active cell.

| Market | Label | Pick odd source |
|--------|-------|-----------------|
| `goals_nl` | `"Over 1.5 Goals"` | `fixtures.goals_over_15_odd` (often NULL) |
| `corners_nl` | `"Over 8.5 Corners"` | `fixtures.corners_over_85_odd` (almost always NULL) |
| `dnb` | Alpha team name | Derived `(1 − p_draw) / p_alpha` |
| `alpha_win` | Alpha team name | `min(home_odd, away_odd)` |

### Emit
The act of writing a pick to `emit_log`. Idempotent via `pick_uuid = sha256("{fixture_id}:{market}:{pick}")[:36]`.

### `write_emit_log()`
Supersede + insert helper in `routes_picks.py`. Before inserting, deletes any stale unsettled pick on the same `(fixture_id, market)` with a different `pick_uuid` (handles alpha team changes mid-window).

### Confidence
`threeway_hit / 100`. Stored on each emit row for reference.

### `pick_odd` NULL
Expected on most goals_nl and all corners_nl rows. Frontend renders `—` via `fmt.odd`. EV will come from Project 3 (breakeven vs live bookmaker price) — not from the stored value.

---

## Settlement Terms

### Settle
Resolve a pick into WIN / VOID / LOSS against the fixture result.
- Persistent: `settle.py` writes `pick_results`.
- On-the-fly: `routes_reports.py` and `routes_diagnostics.py` run `settle_pick()` in memory from emit_log + fixtures + fixture_stats. Used for windows / dashboards that don't need to wait for `settle.py`.

### `pick_results`
| Field | Type | Notes |
|-------|------|-------|
| `pick_uuid` | TEXT | FK to emit_log |
| `settled_at` | TEXT | ISO |
| `outcome` | TEXT | `WIN` / `LOSS` / `VOID` — use this for filters |
| `actual_value` | REAL | `1.0` / `0.0` / `0.5` — use this for arithmetic |

String-vs-number comparisons in SQLite mix storage classes — never use `outcome >= 1`.

### Outcome rules

| Market | WIN | VOID | LOSS |
|--------|-----|------|------|
| goals_nl | `total_goals > line` | — | else |
| corners_nl | `total_corners > line` | — (skipped if NULL) | else |
| dnb | alpha wins | draw | alpha loses |
| alpha_win | alpha wins | — | draw OR alpha loses |

---

## Drift Terms

### Drift
`gap_pp = recent_hit − baseline_hit`. Baseline is the V3.1 historical hit per cell from `V3_MARKETS[…]["hit"]`. Recent is the rolling-window non-loss rate from settled emit_log rows.

### Drift flag

| Flag | Condition |
|------|-----------|
| `stable` | gap > −5pp |
| `watch` | −10pp < gap ≤ −5pp |
| `drifting` | gap ≤ −10pp |
| `no_data` | recent_n < 10 |

---

## Reporting Terms

| Route | Purpose |
|-------|---------|
| `/reports/emit_performance` | Multi-window hit-rate summary (legs + events) — on-the-fly |
| `/reports/emit_recent` | Per-fixture readback with WIN/VOID/LOSS/PENDING — on-the-fly |
| `/reports/emit_market_breakdown` | Per (zone, df, bts, market, pick) hit rates — on-the-fly |
| `/reports/settle_activity` | Per-day settle counts from `pick_results` + last pipeline heartbeat |
| `/inspector/partition_drift` | Per-cell drift across active V3.1 cells |
| `/inspector/recent_settled` | Fixtures with settled picks, grouped |
| `/inspector/similar` | Recent fixtures in the same cell (pre-match lens) |
| `/inspector/daily_calendar` | Per-day WIN/VOID/LOSS calendar |

---

## Process Terms

| Term | Where |
|------|-------|
| Fetch | `fetch_upcoming.py` daily 08:00 SAST |
| Intraday odds refresh | `refresh_odds.py` 14:30 SAST — 8h horizon |
| Score update | `fetch_results.py` 23:30 / 03:00 / 06:00 SAST |
| Corner backfill | `refresh_stats.py` 00:00 SAST — 14d lookback |
| Settlement run | `settle.py` 23:45 / 03:15 / 06:15 SAST |
| Emit pass | `emit_picks.py` 08:05 SAST — calls `/picks?days=3` |
| Recalibrate | Implicit — every `/api/foundation` re-reads settled fixtures |

---

## Tables

| Table | Purpose | Written by | Read by |
|-------|---------|------------|---------|
| `leagues` | League reference (+ Sportmonks id, tier) | `scripts/update_leagues.py`, fetch | everywhere |
| `teams` | Team reference | `fetch_upcoming.py` | fixtures joins |
| `fixtures` | All fixture data | `fetch_upcoming.py`, `refresh_odds.py`, `fetch_results.py` | all routes |
| `fixture_stats` | Corner stats etc. for settled fixtures | `fetch_results.py`, `refresh_stats.py` | `load_foundation`, `settle.py` |
| `emit_log` | Pick emission record | `routes_picks.py` | reports, inspector, settle |
| `pick_results` | Settled pick outcomes | `settle.py` | inspector/recent_settled, daily_calendar, reports/settle_activity |
| `system_health` | Heartbeats — `fetch_upcoming`, `fetch_results`, `settle`, `emit_picks`, `refresh_odds`, `refresh_stats`, legacy `cron_heartbeat` | every daily script | diagnostics, reports |
| `h2h_meetings` | Head-to-head history | seed | (reserved for Project 3) |

---

## What Does Not Exist

| Missing | Note |
|---------|------|
| PRX9 layer | Retired in V3.1 — `/picks/prx9` removed |
| Effective-line fallback for goals_nl / corners_nl | Explicit policy — natural line only |
| Goals/corners system-line picks | Foundation metrics only; not pick markets |
| External cron daemon | Task Scheduler runs the 12 daily jobs |
| Real-money execution | Engine recommends; KK places bets manually |
| Live in-play pick generation | Picks fire on pre-match odds only |
