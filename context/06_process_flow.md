# OddsFlow V4 — Fixture Lifecycle Process Flow (V3.1)

Every phase a fixture moves through from API fetch to historical data.
Every function, table, field, and feedback loop documented as it exists today.

---

## Overview

```
[Sportmonks API]
       |
  Phase 1: FETCH (fetch_upcoming.py — daily)
       |
  Phase 2: LAND (fixtures table + auto draw_zone/bts_pocket write)
       |
  Phase 3: CLASSIFY (zone × DF × bts on-the-fly + stored)  <──────┐
       |                                                          │
  Phase 4: CALIBRATE (compute_foundation — display only)          │
       |                                                          │
  Phase 5: EMIT (V3.1 V_ACTIVE lookup → emit_log)                 │
       |                                                          │
  Phase 6: DISPLAY (Picks tab)                                    │
       |                                                          │
  Phase 7: OBSERVE (Upcoming + Inspector pre-match lens)          │
       |                                                          │
  [Match plays — external event]                                  │
       |                                                          │
  Phase 8: SCORE UPDATE (fetch_results.py — multiple daily passes)│
       |                                                          │
  Phase 9: SETTLE (settle.py → pick_results)                      │
       |                                                          │
  Phase 10: REPORT (Reports + Inspector tabs)                     │
       |                                                          │
  Phase 11: RECALIBRATE (foundation re-reads settled fixtures) ──>┘
       |
  Phase 12: VALIDATE (drift — recent vs baseline per cell)
       |
  [Fixture is historical data — feeds Phase 4 forever]
```

---

## Phase 1: FETCH

**Script:** `fetch_upcoming.py`. Trigger: Task Scheduler 08:00 SAST (and intraday refresh via `refresh_odds.py` at 14:30 SAST).
**API endpoint:** `GET /v3/football/fixtures/between/{start}/{end}?include=participants;odds`
**League filter:** `ACTIVE_LEAGUES` dict — 30 subscribed leagues by `sportmonks_id → tier`.

Monthly windows. `max_pages = 30` for the July–October dense window, `max_pages = 20` otherwise.

**Odds extracted:**

| Field | Sportmonks market_id | Notes |
|-------|---------------------|-------|
| `home_odd` / `draw_odd` / `away_odd` | 1 (1X2) | Always available for tier-1 fixtures |
| `btts_yes_odd` / `btts_no_odd` | 14 | Drives bts_pocket |
| `goals_over_15_odd` / `goals_over_25_odd` / `goals_over_35_odd` | 7 (Goal Line) | Over 1.5 rarely quoted — many NULLs |
| `corners_over_75_odd` / `corners_over_85_odd` / `corners_over_95_odd` | (Asian Total Corners) | Over 8.5 rarely quoted — almost always NULL |

**Kickoff datetime:** Stored as `"YYYY-MM-DD HH:MM:SS"` from `starting_at`.

---

## Phase 2: LAND

**Table written:** `fixtures`. Idempotent — `UPDATE` on `sportmonks_id` match, `INSERT` otherwise.

**Fields written on insert/update:** league_id (resolved via `_league_id_map` to internal `leagues.id` FK), date (kickoff UTC), team FKs and names, all extracted odds, `draw_zone`, `bts_pocket` (V3.1 writes both on insert/update).

`draw_zone` and `bts_pocket` are also backfilled on existing rows via `migrate_write_zones.py`.

---

## Phase 3: CLASSIFY

**Function:** `classify_fixture(row)` → `{zone, bts_pocket, df, tier}`.

- `zone_of(draw_odd)` → strong | standard | low | one_sided | None
- `bts_of(yes_odd, no_odd)` → strong_over | slight_over | slight_under | strong_under | None
- `df_of(home_odd, away_odd)` → DF0 | DF1 | DF2 (rounded `|diff|`)

Cells live in `(zone, df, bts_pocket)` space — 4 × 3 × 4 = 48 possible, 20 active in V3.1.

---

## Phase 4: CALIBRATE (display only)

**When:** every call to `/api/foundation`.
**Function:** `compute_foundation(load_foundation(conn))` in `app/engine/promotion.py`.
**Reads:** all settled fixtures with full odds. Joins `fixture_stats` for corners.

Per cell hit rates: `gn_hit`, `gs_hit`, `cn_hit`, `cs_hit`, `threeway_hit`.
Promotion thresholds: PROMOTE ≥ 72.0%, PROMOTE_TOLERANCE 67.5–71.9% (drop-rank qualified), HOLD, NO.
`LOW_ZONE_SUPPRESS = True` here — low cells show `MEASURING` in the matrix (not used for picks).

**Pick firing does NOT use this matrix.** Picks fire from `static_policy.V3_ACTIVE`.

---

## Phase 5: EMIT

**Route:** `GET /picks?days=N` — `app/api/routes_picks.py`.

Per upcoming fixture in window:

1. Classify → (zone, df, bts).
2. Look up `V3_ACTIVE[(zone, df, bts)]`. Skip if absent (counted as `partition_not_promoted`).
3. For each market in the cell's V3_MARKETS config (one or two per cell):
   - **goals_nl** → label `"Over 1.5 Goals"`, `pick_odd = fixtures.goals_over_15_odd` (often NULL by design).
   - **corners_nl** → label `"Over 8.5 Corners"`, `pick_odd = fixtures.corners_over_85_odd` (almost always NULL by design).
   - **dnb** → label = alpha team name, `pick_odd = _derive_dnb_odd(home_odd, draw_odd, away_odd)`.
   - **alpha_win** → label = alpha team name, `pick_odd = min(home_odd, away_odd)`.
4. Compute drift via `_compute_cell_drift()`.
5. Write to `emit_log` through `write_emit_log()` — supersedes any stale unsettled pick on the same (fixture_id, market) when alpha label changed, then `INSERT OR IGNORE` on `pick_uuid` = `sha256("{fixture_id}:{market}:{pick}")[:36]`.

**Trigger:** scheduler runs `emit_picks.py` daily at 08:05 SAST (calls `/picks?days=3`). Any SPA visit to the Picks tab also drives emits since `/picks` is the endpoint.

---

## Phase 6: DISPLAY

**SPA tab:** Picks (default). JS calls `/picks?days=N`, renders cards with:
fixture, league, kickoff (UTC → local), partition key (`zone:DF:bts`), market row(s), pick label, pick_odd (or `—` via `fmt.odd` when NULL), drift chip.

---

## Phase 7: OBSERVE (pre-match)

- **Upcoming tab:** `GET /upcoming?days=7&tier=T` — every upcoming fixture with classification, regardless of policy match. V3.1 cell chip shown when the (zone, df, bts) is promoted.
- **Inspector tab:**
  - `GET /inspector/partition_drift` — per-cell drift across active V3.1 cells.
  - `GET /inspector/similar?fixture_id=…` — recent fixtures in the same cell (closes the V3 pre-match-lens gap).
  - `GET /inspector/recent_settled` and `/daily_calendar` — settled performance views.

---

## Phase 8: SCORE UPDATE

**Script:** `fetch_results.py`. Triggers: 23:30 SAST (Europe), 03:00 SAST (South America), 06:00 SAST (Dawn SA catch-up — M3 fix).

Fetches `fixtures/between/{start}/{end}?include=scores;statistics;participants`. Writes:

- `fixtures.home_score`, `away_score`, `total_goals`, `status='settled'`
- `fixture_stats.home_corners`, `away_corners`, `total_corners` (parsed from `type_id=34`)

Corner stats can arrive late from Sportmonks; `refresh_stats.py` at 00:00 SAST does a 14-day lookback backfill.

---

## Phase 9: SETTLE

**Script:** `settle.py`. Triggers: 23:45 / 03:15 / 06:15 SAST (mirrors Phase 8 schedule).

Reads pending emit_log rows (no `pick_results` entry, fixture has `home_score`).
LEFT JOINs `fixture_stats` for corners_nl. Resolves per market:

| Market | Rule |
|--------|------|
| `goals_nl` | `total_goals > line` (line parsed from label via regex `"Over (\d+\.5) Goals"`) |
| `corners_nl` | `total_corners > line` (regex `"Over (\d+\.5) Corners"`) — skipped if NULL |
| `dnb` | alpha wins → WIN (1.0); draw → VOID (0.5); else LOSS (0.0) |
| `alpha_win` | alpha wins → WIN; else LOSS |

Writes `pick_results(pick_uuid, settled_at, outcome, actual_value)` and a `settle` heartbeat to `system_health`.

---

## Phase 10: REPORT

| Route | Reads | Notes |
|-------|-------|-------|
| `/reports/emit_performance` | emit_log + fixtures (on-the-fly settle) | 1d/3d/7d/30d/90d/180d windows |
| `/reports/emit_recent` | emit_log + fixtures | Per-fixture readback |
| `/reports/emit_market_breakdown` | emit_log + fixtures | Per (zone, df, bts, market, pick) hit rates |
| `/reports/settle_activity` | pick_results + system_health | Per-day settle counts; last_clean_run from any pipeline metric |
| `/inspector/recent_settled` | pick_results JOIN emit_log JOIN fixtures | Settled picks grouped by fixture |
| `/inspector/daily_calendar` | pick_results | Per-day WIN/VOID/LOSS counts |

---

## Phase 11: RECALIBRATE

`load_foundation(conn)` re-queries `WHERE home_score IS NOT NULL` on every `/api/foundation` call.
New scored fixtures enter the matrix automatically. Promotion statuses can shift between sessions.
Pick firing is unaffected (V3.1 is static).

---

## Phase 12: VALIDATE

`_compute_cell_drift()` in `routes_picks.py` and `compute_drift_rows()` in `routes_inspector.py`:

Gap = recent_hit − baseline_hit (pp). Flags: `stable` / `watch` / `drifting` / `no_data`.
Drift is informational; the engine never auto-suppresses a drifting cell. Operator reviews and decides.

Hit rate convention: **V3 non-loss** — voids count as wins (`(wins + voids) / settled`). Restored in Session 16 after a Wilson-style attempt.

---

## Connection map

```
fetch_upcoming.py  → fixtures (incl. draw_zone, bts_pocket on insert/update) + teams + leagues map
refresh_odds.py    → fixtures (odds-only update for next-8h fixtures)
fetch_results.py   → fixtures (scores) + fixture_stats (corners)
refresh_stats.py   → fixture_stats (late-arriving corner backfill)

routes_picks.py
  ← V3_ACTIVE (static_policy.py)
  ← fixtures (upcoming in window)
  → classify_fixture()  (zone × df × bts)
  → _compute_cell_drift()
  → write_emit_log()  → emit_log

settle.py
  ← emit_log (pending)
  ← fixtures + fixture_stats
  → pick_results
  → system_health (heartbeat)

routes_inspector.py / routes_reports.py / routes_diagnostics.py
  ← emit_log + pick_results + fixtures + fixture_stats + system_health
```

---

## What does not exist

| Item | Why |
|------|-----|
| PRX9 ranking layer | Retired with V3 — `/picks/prx9` removed in V3.1 (2026-05-28) |
| Effective-line fallback for goals_nl / corners_nl | Explicit V3 decision — natural line only. `pick_odd` NULL is expected. |
| Goals/corners _system-line_ picks | V3.1 only fires the natural line; system line is a foundation metric, not a pick. |
| External cron / dedicated job queue | Single-user Windows host — Task Scheduler runs the 12 jobs. |
| Real-money execution | Engine is a recommender. Operator places bets by hand on bookmaker sites. |
