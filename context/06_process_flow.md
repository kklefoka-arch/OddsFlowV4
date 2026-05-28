# OddsFlow V4 — Fixture Lifecycle Process Flow (V3)

Every phase a fixture moves through, V3 architecture as restored Session 19.

---

## Overview

```
[Sportmonks API]
       |
  Phase 1: FETCH (fetch_upcoming.py — daily)
       |
  Phase 2: LAND (fixtures table + draw_zone/bts_pocket write)
       |
  Phase 3: CLASSIFY (zone × bts on-the-fly + stored)  <──────┐
       |                                                     │
  Phase 4: CALIBRATE (compute_foundation — display only)     │
       |                                                     │
  Phase 5: EMIT (V3_ACTIVE lookup → emit_log)                │
       |                                                     │
  Phase 6: DISPLAY (Picks tab)                               │
       |                                                     │
  Phase 7: OBSERVE (Upcoming + Inspector pre-match lens)     │
       |                                                     │
  [Match plays — external event]                             │
       |                                                     │
  Phase 8: SCORE UPDATE (fetch_results.py — 3 daily passes)  │
       |                                                     │
  Phase 9: SETTLE (settle.py → pick_results)                 │
       |                                                     │
  Phase 10: REPORT (Reports + Inspector tabs)                │
       |                                                     │
  Phase 11: RECALIBRATE (foundation re-reads settled) ───────┘
       |
  Phase 12: VALIDATE (drift — recent vs baseline per cell)
       |
  [Fixture is historical data — feeds Phase 4 forever]
```

---

## Phase 1: FETCH

`fetch_upcoming.py`. Task Scheduler 08:00 SAST + intraday `refresh_odds.py` 14:30 SAST.
API: `GET /v3/football/fixtures/between/{start}/{end}?include=participants;odds`.
League filter: `ACTIVE_LEAGUES` (30 leagues).
Monthly windows; max_pages=30 (Jul–Oct), =20 elsewhere.

**Odds extracted:**

| Field | Sportmonks market_id | Notes |
|-------|---------------------|-------|
| `home_odd` / `draw_odd` / `away_odd` | 1 (1X2) | Always available for T1 |
| `btts_yes_odd` / `btts_no_odd` | 14 | Drives bts_pocket |
| `goals_over_15_odd` / `goals_over_25_odd` / `goals_over_35_odd` | 7 (Goal Line) | Over 1.5 rarely quoted — many NULLs |
| `corners_over_75_odd` / `corners_over_85_odd` / `corners_over_95_odd` | (Corners totals) | Over 8.5 rarely quoted — almost always NULL |

**Kickoff datetime:** Stored as `"YYYY-MM-DD HH:MM:SS"`.

---

## Phase 2: LAND

`fixtures` table. Idempotent — UPDATE on `sportmonks_id` match, INSERT otherwise.
Fields written: league_id (resolved via `_league_id_map` to internal `leagues.id`), `date` (kickoff UTC), team FKs and names, all extracted odds, `draw_zone`, `bts_pocket`.
`draw_zone` was re-backfilled in Session 19 with the raw-notes boundaries on all existing rows (8,145 updates).

---

## Phase 3: CLASSIFY

`classify_fixture(row)` → `{zone, bts_pocket, tier}`.

- `zone_of(draw_odd)` → strong | standard | low | one_sided | None (V3 + raw-notes overlay)
- `bts_of(yes_odd, no_odd)` → strong_over | slight_over | slight_under | strong_under | None

Cells live in `(zone, bts_pocket)` — 4 × 4 = 16 possible, 9 active in V3.

---

## Phase 4: CALIBRATE (display only)

`compute_foundation(load_foundation(conn))` in `app/engine/promotion.py` on every `/api/foundation` call. Reads all settled fixtures with full odds; joins `fixture_stats` for corners.
Per cell: `gn_hit`, `gs_hit`, `cn_hit`, `cs_hit`, `threeway_hit`. PROMOTE thresholds: ≥ 72.0% / PROMOTE_TOLERANCE 67.5–71.9% (drop-rank qualified) / HOLD / NO.
`LOW_ZONE_SUPPRESS = True` here — low cells display `MEASURING`. Pick firing does NOT use this matrix; that's `V3_ACTIVE`.

---

## Phase 5: EMIT

`GET /picks?days=N` — `app/api/routes_picks.py`.

Per upcoming fixture in window:
1. Classify → (zone, bts).
2. Look up `V3_ACTIVE[(zone, bts)]`. Skip if absent (counted as `partition_not_promoted`).
3. For each market in the cell's config:
   - **goals_nl** → label `"Over 1.5 Goals"`, `pick_odd = fixtures.goals_over_15_odd` (often NULL by design).
   - **corners_nl** → label `"Over 8.5 Corners"`, `pick_odd = fixtures.corners_over_85_odd` (almost always NULL by design).
   - **dnb** → label = alpha team name, `pick_odd = _derive_dnb_odd(home, draw, away)`.
   - **alpha_win** → label = alpha team name, `pick_odd = min(home_odd, away_odd)`.
4. Compute drift via `_compute_cell_drift()` (V3 non-loss).
5. Write to `emit_log` through `write_emit_log()` — supersedes stale unsettled pick on (fixture_id, market) with different `pick_uuid`, then `INSERT OR IGNORE` (pick_uuid = sha256("{fixture_id}:{market}:{pick}")[:36]).

Scheduler: `emit_picks.py` calls `/picks?days=3` daily at 08:05 SAST. SPA Picks tab loads also drive emits.

---

## Phase 6: DISPLAY

SPA Picks tab. `/picks?days=N` → cards with fixture, league, kickoff, partition key (`zone:bts`), market row(s), pick label, pick_odd (or `—` via `fmt.odd`), drift chip.

---

## Phase 7: OBSERVE (pre-match)

- **Upcoming tab:** `GET /upcoming?days=7&tier=T` — every upcoming fixture with classification. V3 cell chip when (zone, bts) is promoted.
- **Inspector tab:**
  - `GET /inspector/partition_drift` — drift per V3 cell.
  - `GET /inspector/similar?fixture_id=…` — recent fixtures in same (zone, bts) cell.
  - `GET /inspector/recent_settled` and `/daily_calendar` — settled performance views.

---

## Phase 8: SCORE UPDATE

`fetch_results.py`. Triggers: 23:30 SAST (Europe), 03:00 SAST (SA), 06:00 SAST (Dawn SA catch-up — M3).
Fetches `?include=scores;statistics;participants`. Writes:
- `fixtures.home_score`, `away_score`, `total_goals`, `status='settled'`
- `fixture_stats.home_corners`, `away_corners`, `total_corners` (parsed from `type_id=34`)

`refresh_stats.py` at 00:00 SAST does a 14-day corner-stats backfill.

---

## Phase 9: SETTLE

`settle.py`. Triggers: 23:45 / 03:15 / 06:15 SAST.
Reads pending emit_log rows (no `pick_results` entry, fixture has `home_score`). LEFT JOINs `fixture_stats` for corners_nl.

| Market | Rule |
|--------|------|
| `goals_nl` | `total_goals > line` (line parsed via regex `"Over (\d+\.5) Goals"`) |
| `corners_nl` | `total_corners > line` (regex `"Over (\d+\.5) Corners"`); skipped if NULL |
| `dnb` | alpha wins → WIN; draw → VOID; else LOSS |
| `alpha_win` | alpha wins → WIN; else LOSS |

Writes `pick_results(pick_uuid, settled_at, outcome, actual_value)` and `settle` heartbeat.

---

## Phase 10: REPORT

| Route | Reads | Notes |
|-------|-------|-------|
| `/reports/emit_performance` | emit_log + fixtures | On-the-fly settle. 1d/3d/7d/30d/90d/180d windows |
| `/reports/emit_recent` | emit_log + fixtures | Per-fixture readback |
| `/reports/emit_market_breakdown` | emit_log + fixtures | Per (zone, bts, market, pick) hit rates |
| `/reports/settle_activity` | pick_results + system_health | Per-day counts; last_clean_run from any pipeline metric |
| `/inspector/recent_settled` | pick_results JOIN emit_log JOIN fixtures | Settled picks grouped |
| `/inspector/daily_calendar` | pick_results | Per-day WIN/VOID/LOSS calendar |

---

## Phase 11: RECALIBRATE

`load_foundation(conn)` re-queries `WHERE home_score IS NOT NULL` on every `/api/foundation` call. New scored fixtures enter the matrix automatically. Pick firing is unaffected (V3 is static).

---

## Phase 12: VALIDATE

`_compute_cell_drift()` in `routes_picks.py` + `compute_drift_rows()` in `routes_inspector.py`.
Gap = `recent_hit − baseline_hit` (pp). Flags: `stable` / `watch` / `drifting` / `no_data`.
Hit rate convention: **V3 non-loss** — voids count as wins.

---

## Connection map

```
fetch_upcoming.py  → fixtures (incl. draw_zone, bts_pocket) + teams + leagues map
refresh_odds.py    → fixtures (odds-only update for next-8h)
fetch_results.py   → fixtures (scores) + fixture_stats (corners)
refresh_stats.py   → fixture_stats (late corner backfill)

routes_picks.py
  ← V3_ACTIVE (static_policy.py)  — 9 cells, 2-key
  ← fixtures (upcoming in window)
  → classify_fixture()  (zone × bts)
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

## What does not exist (by Durable Rule)

| Item | Why |
|------|-----|
| DF as partition key | Removed Session 19. May return only after 6 weeks of post-overlay V3 settlement validates. |
| EV / breakeven gates | Project 2 analysis is reference-only — no live engine code consults it. |
| PRX9 ranking layer | Retired. |
| Effective-line fallback for goals_nl / corners_nl | Natural line only. |
| Goals/corners system-line picks | Foundation metrics only. |
| External cron daemon | Task Scheduler runs the 12 jobs. |
| Real-money execution | Engine recommends; KK places bets manually. |
| Live in-play pick generation | Pre-match odds only. |
