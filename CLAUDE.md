# OddsFlow V4 — V3.2 Engine (Session 23c, DF re-introduced — Rule 1 overridden)

**This is the only OddsFlow project.** One folder, one repo, one DB.
Read this file at the start of every session. Update it at the end. Commit it.

Operator: Katlego (KK) | Port: 8083 | Repo: `github.com/kklefoka-arch/OddsFlowV4`
Host (local): `http://localhost:8083` | Host (ngrok): `https://steadier-legwarmer-finlike.ngrok-free.dev`

---

## Project overview

Football betting analytics engine. Ingests pre-match fixtures and odds from Sportmonks, classifies each fixture into a **(draw_zone × BTS pocket)** cell, and emits picks for the 9 cells in the V3 static policy. The structured edge is in the partition — `draw_odd × bts_parent` reveals the layer where hit rates concentrate. Project 2 calibration confirmed that thesis; it has no role in the live engine until 6 weeks of pure V3 settlement validates it (Notes 27-05).

**V3 policy (Session 11 baseline, restored Session 19 — 2026-05-28):**
9 active cells, 4 markets. Hit rate is the only edge metric. No EV gates, no economic models, no DF as a partition key.

## Durable rules (do not violate without operator approval)

These rules exist because Sessions 12–18 drifted away from Project 1 — DF got introduced as a partition key, EV calibration findings retrofitted into the engine, doc state diverged. Session 19 (this) restores the framework. Future sessions must hold this line.

0. **The engine reads structural patterns from odds, not from form/position/attack stats.** Bookmaker odds (`draw_odd`, `btts_yes/no_odd`, `home_odd`, `away_odd`) are the market's compressed consensus across every signal a traditional analyst would weigh. The (zone × DF × bts) partition reveals the structural regions where outcomes concentrate — and the engine's edge is reading those regions directly, not re-deriving them from surface features. When an engine pick disagrees with conventional analysis ("they're in poor form", "their attack is weak"), trust the partition's historical hit rate. The market priced what it priced for a reason; the engine reads that pricing back. Results validate; pundits don't.
1. **~~No DF as partition.~~ OVERRIDDEN by operator decision Session 23c (2026-05-29).** `df_of()` is restored to `classify.py`. The partition is now `(zone, DF, bts_pocket)`, 3-key. DF buckets: DF0 / DF1 / DF2. Re-built under the Session-19 raw-notes boundary overlay (`Scripts/build_v32_df_policy.py` in the AI Website project). Session 17 enhanced analysis (20-30pp DF separation) plus the v3.2 rebuild (12.8pp lift on strong:slight_under dnb across DF buckets) supplied the evidence. The previous "wait 6 weeks first" precondition is waived.
2. **No EV / economic models in the live engine.** Breakeven odds, EV, Wilson intervals — all stay in the analysis folder. The live engine measures, emits, settles, and reports hit rate. Nothing else gates picks. **This rule is unchanged.**
3. **Hit rate is the V3 non-loss convention.** `(wins + voids) / settled`. Voids (DNB draws) count as hits. Wilson is out. **This rule is unchanged.**
4. **Calibration cycle.** Project 2-style calibration runs *after* 6 weeks of live settlement — the clock for V3.2 starts 2026-05-29. EV/breakeven layers may be re-evaluated then; they are NOT in the live engine until that gate clears.
5. **Per-market display.** Each market — goals_nl, corners_nl, dnb, alpha_win — has its own settlement count and hit-rate display per partition. Not blended. Not weighted outside the hit-rate foundation.
6. **Foundation matrix splits on T1 and T2+T3.** Tier slices live; mixed tiers are noise.
7. **No team form / position / predicted-uncertainty weighting.** Only odds drivers (zone × bts) + H2H corner counts (counts, not averages) are valid signals. Anything beyond those is research, not engine.

## Current state — V3.2 DF-aware partition (Session 23c, 2026-05-29)

**20 active cells, 3-key `(zone, DF, bts_pocket)`.** Golden-Rule market set per zone retained from V3. Build run on the live DB under the raw-notes overlay; min_n=45 (operator-approved), min_corners_n=30. Per-zone distribution:

- **strong (6 cells):** DF0/DF1/DF2 × {slight_over, slight_under} → `goals_nl` O1.5 + `dnb`
- **standard (6 cells):** DF0:slight_over, DF0:strong_over, DF1:slight_over, DF1:strong_over, DF2:slight_over, DF2:slight_under → `goals_nl` O1.5 + `corners_nl` O8.5 + `dnb`
- **low (4 cells):** DF1:strong_over, DF2:{slight_over, slight_under, strong_over} → `dnb` + `goals_nl` O2.5
- **one_sided (4 cells):** DF2 × {slight_over, slight_under, strong_over, strong_under} → `alpha_win` + `goals_nl` O2.5

**DF separation visible in the cells** (the evidence that justified the Rule 1 override):
- strong:slight_under dnb: DF0 66.9% → DF1 71.4% → DF2 79.7% (**+12.8pp lift**)
- standard:slight_over dnb: DF0 65.7% → DF1 70.2% → DF2 78.1% (**+12.4pp lift**)
- standard:slight_over goals_nl: DF0 76.3% → DF1 77.8% → DF2 75.2% (flat — line check)

**10 sub-cells excluded by min_n=45** — structurally rare combinations (DF0 in low/one_sided, DF1 in one_sided, strong_under in strong/standard).

**Why two emits per fixture:** the 3-way pick (DNB or alpha_win) measures the market's structural confidence in the favourite; the line pick (goals_nl or corners_nl) measures the over-total expectation. Both are natural-line by zone — no system-line or effective-line fallbacks. The 3-picks-log layer (deferred) chooses which combination of legs to assemble into a practical bet based on edge vs bookmaker price.

## Zone boundaries (raw-notes overlay)

Updated Session 19 from the original V3 cutoffs because one_sided fixtures crept into low under the prior boundaries, contaminating low-zone hit rates around 50% and bleeding into standard.

| Zone | draw_odd range | Notes |
|------|---------------|-------|
| (excluded) | `draw_odd < 2.90` | both_sided — too draw-heavy, not in policy |
| `strong` | `2.90 ≤ draw_odd < 3.30` | |
| `standard` | `3.30 ≤ draw_odd < 3.80` | The cleanest cell — evidence consistently points here |
| `low` | `3.80 ≤ draw_odd < 4.30` | Was 4.10–4.80 under V3 prior — too wide, picked up extreme favourites |
| `one_sided` | `draw_odd ≥ 4.30` | Was ≥ 4.80 — pulled down so genuine one-sided favourites are isolated |

Baselines in `static_policy.V3_MARKETS` and `PROMOTED_CELLS` are now computed under the post-overlay boundaries (Session 19) — see the file header. The 6-week settlement watch validates whether they hold up live.

## Key files

| File | Purpose |
|------|---------|
| `fetch_upcoming.py` | Daily — refresh pre-match odds (1X2, BTTS, goals_over_15/25/35, corners_over_75/85/95) + kickoff datetimes |
| `emit_picks.py` | Calls local `/picks?days=3` to materialise picks + writes heartbeat |
| `refresh_odds.py` | Intraday odds refresh for next-8h fixtures (M2) |
| `refresh_stats.py` | Corner-stats backfill (14d lookback, M3) |
| `fetch_results.py` | After matches — scores + fixture_stats |
| `settle.py` | After fetch_results — pick_results writer (goals_nl, corners_nl, dnb, alpha_win) |
| `app/engine/static_policy.py` | `V3_ACTIVE` / `V3_MARKETS` / `PROMOTED_CELLS` — 9-cell V3 policy |
| `app/engine/classify.py` | `zone_of()` (raw-notes boundaries) + `bts_of()` |
| `app/engine/promotion.py` | `compute_foundation()` — display matrix only, not pick firing |
| `app/api/routes_picks.py` | `/picks` — reads `V3_ACTIVE`, supersede logic |
| `app/api/routes_foundation.py` | `/api/foundation` — Analysis tab |
| `app/api/routes_diagnostics.py` | Multi-metric cron heartbeat across the 7 daily pipeline tasks |
| `data/oddsflow_v4.db` | Live SQLite DB (not in git). Backups under `data/oddsflow_v4.db.bak.*` |

## Daily flow

Same as before — Task Scheduler runs the 12 jobs from `setup_scheduler.ps1`. Manual chain: `.\run_daily.ps1` (fetch_upcoming → emit_picks → fetch_results → settle).

| Time SAST | Task | Script |
|-----------|------|--------|
| At system start | OddsFlow_Server / OddsFlow_Ngrok | uvicorn + ngrok auto-restart |
| 00:00 | OddsFlow_RefreshStats | refresh_stats.py — late-corners backfill |
| 03:00 / 03:15 | OddsFlow_FetchResults_SA / Settle_SA | South American window |
| 06:00 / 06:15 | OddsFlow_FetchResults_DawnSA / Settle_DawnSA | Late SA catch-up (M3) |
| 08:00 / 08:05 | OddsFlow_FetchUpcoming / EmitPicks | Daily pre-match refresh + emit |
| 14:30 | OddsFlow_RefreshOdds | Intraday refresh for next-8h fixtures (M2) |
| 23:30 / 23:45 | OddsFlow_FetchResults / Settle | European window close |

## Decisions made

- **V3 restored (Session 19, 2026-05-28).** Picks fire from `V3_ACTIVE` (9 cells, 2-key). DF removed from classify and from all route lookups. `compute_foundation()` still serves the `/api/foundation` display.
- **Zone boundaries shifted to raw-notes overlay** (2.90 / 3.30 / 3.80 / 4.30). Fixtures DB re-backfilled — 8,145 `draw_zone` updates.
- **`df_level` columns retained on fixtures + emit_log** as additive historical metadata. New emit rows write NULL.
- **Markets per Golden Rule (Session 19 extension):** strong → goals_nl O1.5 + dnb; standard → goals_nl O1.5 + corners_nl O8.5 + dnb; low → dnb + goals_nl O2.5; one_sided → alpha_win + goals_nl O2.5.
- **Goals NL pick label** parses via regex `r"Over (\d+\.5) Goals"` — both `Over 1.5 Goals` (strong/standard) and `Over 2.5 Goals` (low/one_sided) settle correctly.
- **Corners NL pick label** "Over 8.5 Corners" — `settle.py` regex `r"Over (\d+\.5) Corners"`.
- **Goals NL natural-line only by zone** — Over 1.5 for strong/standard, Over 2.5 for low/one_sided. No effective-line fallback. `pick_odd` NULL on most goals_nl / all corners_nl rows is expected; SPA renders `—` via `fmt.odd`.
- **`write_emit_log()`** supersedes stale unsettled picks when alpha team label changes.
- **fetch_upcoming.py** stores full kickoff datetimes; monthly windows; max_pages=30 (Jul–Oct), =20 elsewhere.
- **`fixtures.league_id`** stores internal DB `leagues.id` (via `_league_id_map`).
- **Hit-rate convention** = V3 non-loss (voids count as 1). Wilson reverted in Session 16.

## Pending / next

- Monitor V3 + Golden Rule settlement under new boundaries for 6 weeks. Recalibrate baseline hit rates after that.
- Once recalibrated, decide whether DF should be re-introduced as a partition refinement (or stay an analytical signal). Until then, rule 1 holds.
- **3-picks-log layer (deferred build):** new SPA tab + `bet_tickets` table per Notes expand 28-05-26. Translates V3 emits into practical multibet / system-bet structures with 72-hour locked windows. All EV / breakeven math lives here, not in the engine. Runs in parallel to the 6-week watch and gives faster feedback on whether the structural edge translates to +EV at bookmaker prices.
- Project 3 (live odds comparison vs breakeven) stays in draft in the AI Website folder. Build only after Project 1 validates under the new boundaries.
- `low:strong_under` (n=18) remains deferred — re-evaluate after 6-week post-overlay settlement when sample grows. All other "high BTS" cells (low:strong_over, one_sided:strong_over, one_sided:strong_under) added Session 19+ per operator clarification.

## Reference documents

| Doc | Contents |
|-----|----------|
| `context/01_project_overview.md` | What / who / why (V3 + overlay) |
| `context/02_league_config.md` | 30 leagues, tier assignments |
| `context/03_engine_rules.md` | Classification (zone × bts) + V3 policy + new boundaries |
| `context/04_current_status.md` | Current state, known issues, session log |
| `context/05_architecture.md` | File map, process flow, API routes, DB tables |
| `context/06_process_flow.md` | Full fixture lifecycle |
| `context/07_system_language.md` | Every term defined; what exists vs what does not |
| `context/engine_knowledge.md` | Tabs + abbreviations + operating notes |
| `context/plan_group1/2/3` | Historical implementation plans (IMPLEMENTED — audit trail) |

## Session checklist

On start: scan directory → read CLAUDE.md → read `context/04_current_status.md`
On end: update `context/04_current_status.md` → update this file → commit → push

**Special rule:** if a session ends with a change to `static_policy.py`, `classify.py`, `promotion.py`, or zone/df logic anywhere — explicitly call out which Durable Rule (above) was affected and why the operator approved it. Default: do not change.
