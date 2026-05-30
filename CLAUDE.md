# OddsFlow V4 — v4 Engine (zone × BTS yes/no, 8 cells; spread/DF/H2H as signals)

**This is the only OddsFlow project.** One folder, one repo, one DB.
Read this file at the start of every session. Update it at the end. Commit it.

Operator: Katlego (KK) | Port: 8083 | Repo: `github.com/kklefoka-arch/OddsFlowV4`
Host (local): `http://localhost:8083` | Host (ngrok): `https://steadier-legwarmer-finlike.ngrok-free.dev`

---

## Project overview

Football betting analytics engine. Ingests pre-match fixtures and odds from Sportmonks, classifies each fixture into a **(draw_zone × BTS direction)** cell, and emits picks for the cells in the v4 policy. The structured edge is in the partition — `draw_odd × bts(yes/no)` reveals the layer where hit rates concentrate.

**Two-layer architecture:**
- **v4 engine (this app):** `(zone × bts)` partition where `bts ∈ {over, under}` — **8 cells, hit-rate only**. The BTS strong/slight **spread**, **DF**, and the **H2H-corner** count are *qualifying signals* (confidence chips + one goals-override), NOT partition axes. No EV, no Wilson. No hard suppression gates.
- **Advanced "Picks Log" layer:** Most-likely / Mean / Optimistic 72h-locked configs built *on the back of* the engine. **EV / economic modelling belongs here, never in the engine.** Currently legs-only (no EV yet, by design — introduced only after the build is validated in full).

**v4 policy (2026-05-30):** 8 active cells, 2-key `(zone, bts)`, 3 markets per cell (goals_nl O1.5 / corners_nl O7.5(strong)·O8.5 / threeway alpha-or-draw). Drawn from a fresh from-scratch test + adversarial feasibility workflow (GO_WITH_CONDITIONS) in `C:\OddsFlow V4 Website\` (`policy/v4_policy.md`, `test/sheets/v4_test_2026-05-30.xlsx`).

**Data foundation:** full-capture landing (`raw_odds_json` on fixtures, `raw_stats_json` on fixture_stats — nothing the API returns leaks unaccounted). **Odds are frozen at settlement** (refresh_odds only touches `home_score IS NULL`; fetch_upcoming skips past-dated fixtures) — so averages/calcs use the odds the fixture settled on *our* system, never the live source. `odds_updated_at` stamps freshness; refresh widened to 30h pre-KO. H2H-corner signal is derived local-first from our own prior meetings (live on upcoming fixtures). User surface: `/board` (Picks / Results / Performance / Picks-Log).

## Durable rules (do not violate without operator approval)

These rules exist because Sessions 12–18 drifted away from Project 1 — DF got introduced as a partition key, EV calibration findings retrofitted into the engine, doc state diverged. Session 19 (this) restores the framework. Future sessions must hold this line.

0. **The engine reads structural patterns from odds, not from form/position/attack stats.** Bookmaker odds (`draw_odd`, `btts_yes/no_odd`, `home_odd`, `away_odd`) are the market's compressed consensus across every signal a traditional analyst would weigh. The (zone × DF × bts) partition reveals the structural regions where outcomes concentrate — and the engine's edge is reading those regions directly, not re-deriving them from surface features. When an engine pick disagrees with conventional analysis ("they're in poor form", "their attack is weak"), trust the partition's historical hit rate. The market priced what it priced for a reason; the engine reads that pricing back. Results validate; pundits don't.
1. **Partition is `(zone, bts)` where `bts ∈ {over, under}` — 8 cells. DF AND the BTS strong/slight spread are SIGNALS, not cell axes.** (v4, 2026-05-30. The BTS axis was reduced to its pure yes/no direction; the strong/slight spread, DF, and H2H-corner are qualifying signals.) Evidence (fresh test + feasibility workflow GO_WITH_CONDITIONS): the 8-cell form matches the old 15-cell on hit-rate with zero thin cells; the spread split spawned dead n=16/19/18 cells and gave tiny/sign-inconsistent gaps; DF is dead in 5/8 cells. The one preserved edge is a **goals-override** (standard:over / low:over fire goals at the strong-spread rate when spread==strong) — a per-market signal, not a cell. `policy/v4_policy.md`. If a future session wants to re-partition on spread/DF, that's an operator decision; document it the same way.
2. **No EV / economic models in the live engine.** Breakeven odds, EV, Wilson intervals — all stay in the analysis folder and the **advanced Picks Log layer**. The ground-zero engine measures, emits, settles, and reports hit rate. Nothing else gates picks. **Unchanged.**
3. **Hit rate convention.** The ground-zero 3-way pick is **alpha-or-draw**: a draw is a protected WIN (no 0.5 void). Hit rate = wins / settled (binary). Legacy `dnb` rows still settle under the old `(wins+voids)/settled` for their tail. Wilson is out. **Re-pinned 2026-05-30 (void retired at ground zero).**
4. **Calibration / EV lives in the advanced layer.** Project 2-style calibration + EV is computed and shown only in the Picks Log layer, never gating ground-zero emission. (The 6-week clock for re-baselining the policy under live-only data starts 2026-05-30.)
5. **Per-market display.** Each market — goals_nl, corners_nl, threeway — has its own settlement count and hit-rate display per partition. Not blended.
6. **Foundation matrix splits on T1+T2 and T3.** (Changed 2026-05-30 from "T1 vs T2+T3" to country-context tiers grouped **T1+T2 vs T3**.) Tier slices live; mixed tiers are noise.
7. **No team form / position / predicted-uncertainty weighting.** Only odds drivers (zone × bts) + the two signals (DF, H2H corner counts — counts, not averages) are valid. Anything beyond those is research, not engine.

## Current state — v4 engine (2026-05-30)

**8 active cells, 2-key `(zone, bts)` where `bts ∈ {over, under}`.** Drawn from a fresh from-scratch test on 28,571 settled fixtures + an adversarial feasibility workflow (GO_WITH_CONDITIONS). All 8 cells have n≥802 — **zero thin cells** (the old 15-cell 4-pocket form carried three n=16/19/18 noise cells; collapsing BTS to its pure direction removed them at equal hit-rate). Evidence + policy in `C:\OddsFlow V4 Website\` (`test/sheets/v4_test_2026-05-30.xlsx`, `policy/v4_policy.md`).

**The 8 cells (composite = mean of the 3 market hit-rates):** strong:over 70.3 · strong:under 69.5 · standard:over 71.3 · standard:under 69.9 · low:over 75.6 · low:under 71.8 · one_sided:over 80.4 · one_sided:under 80.6.

**Markets per cell:** goals_nl **O1.5** (all zones) · corners_nl **O7.5** (strong) / **O8.5** (rest) · threeway **alpha-or-draw** (a draw is a WIN; straight-win lives in the advanced Optimistic config).

**Signals (NOT cell axes — no hard suppression gates in v4):**
- **BTS spread** (strong/slight): display chip + **one goals-override** — in `standard:over` & `low:over`, when spread==strong the goals leg carries the strong-spread rate (83.8% / 85.0%) instead of the blended cell rate. A per-market tilt (Rule 5), not a cell.
- **DF** (DF0/1/2): display chip + threeway-confidence note where monotone (strong:under, standard:over DF2). Dead in 5/8 cells → never a partition.
- **H2H-corner** (over/under/none): display-only, derived **local-first** from our own prior meetings (live on upcoming fixtures).

**Why three markets per fixture:** the 3-way (alpha-or-draw) measures the market's structural confidence in the favourite; goals_nl + corners_nl measure over-total expectation. The advanced **Picks Log** layer derives Most-likely/Mean/Optimistic configs from these emits (legs-only; EV only after full validation).

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
