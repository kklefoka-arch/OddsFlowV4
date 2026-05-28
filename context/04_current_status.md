# Current Status — OddsFlow V4

Update this file at the end of every session.
Last updated: 2026-05-28 (Session 19 — V3.1 doc-drift sweep)

---

## State: Running ✅

| Item | Detail |
|------|--------|
| Folder | `C:\OddsFlowV4` |
| Port | 8083 (local) |
| ngrok | https://steadier-legwarmer-finlike.ngrok-free.dev |
| DB | `data/oddsflow_v4.db` |
| GitHub | `github.com/kklefoka-arch/OddsFlowV4` |
| Active policy | **V3.1** (DF-aware, 20 cells) — `static_policy.V3_ACTIVE` |
| Fixtures | 51,057 total — 46,905 settled, 4,152 upcoming |
| Fixture stats | 38,574 settled with corner stats |
| emit_log | 613 rows — 275 settled, 338 pending |
| pick_results | 275 rows — 156 WIN, 76 LOSS, 43 VOID (non-loss hit 73.5% in 7d window) |
| By market (emit_log) | dnb 293, goals_nl 177, corners_nl 112, alpha_win 31 |
| Leagues | 62 in DB (30 subscribed, 32 historical) — all named + tiered |
| h2h_meetings | 58,881 |
| Live picks via `/picks?days=7` | ~202 across 136 fixtures (varies by window) |

## How to start (Windows)

The server runs from Task Scheduler (`OddsFlow_Server`, at system start). To run manually:

```powershell
Set-Location C:\OddsFlowV4
uvicorn app.main:app --host 0.0.0.0 --port 8083
```

## Daily flow (chained in `run_daily.ps1`)

```powershell
python fetch_upcoming.py    # refresh odds + kickoff datetimes
python emit_picks.py        # call /picks?days=3 → emit_log
python fetch_results.py     # write scores + fixture_stats
python settle.py            # write pick_results
```

The 12 Task Scheduler jobs (see `setup_scheduler.ps1`) run these scripts on staggered schedules
across the European, South American, and SA-dawn windows. See `CLAUDE.md → Scheduler` for the table.

---

## Known issues / observations

| # | Item | Notes |
|---|------|-------|
| 1 | `pick_odd` NULL on 100% of corners_nl and ~95% of goals_nl rows | By design — natural-line-only policy (Over 1.5 Goals / Over 8.5 Corners are trivial overs Sportmonks rarely quotes). SPA renders `—` via `fmt.odd`. EV will be computed via Project 3 (breakeven_odds + bookmaker price comparison), not stored pick_odd. |
| 2 | 96% of upcoming fixtures have no `draw_zone` | Not a bug — 3,985/4,152 upcoming have no `draw_odd` quoted yet by Sportmonks. Within the 7-day window, 41% (146/352) carry odds and classify correctly. `odd_but_no_zone = 0`. |
| 3 | `LOW_ZONE_SUPPRESS` differs between modules | `static_policy.py = False` (pick firing — low zone active). `promotion.py = True` (foundation matrix display — shows low cells as `MEASURING`). Intentional split. |
| 4 | Drift: `one_sided:DF2:slight_over` flagged `drifting` at −14.7pp (recent_n=21) | Early signal — monitor for 2 more weeks before any cell-level action. |
| 5 | `pick_results.outcome` stores string `WIN`/`LOSS`/`VOID` (numeric value lives in `actual_value`) | Filter on `outcome='WIN'` or use `actual_value` for arithmetic. SQLite string-vs-number comparisons silently return garbage. |
| 6 | 11 historical "duplicate" emit_log pairs | Both rows have pick_results (odds flipped mid-session, alpha team changed, both settled). Cannot delete. `write_emit_log()` supersede logic prevents new ones. |

---

## Session log

| Session | Date | Work done |
|---------|------|-----------|
| 1–8 | 2026-05-22 → 2026-05-24 | V4 built, SPA + 7 tabs, league fixes, classification + matrix wired, fetch_results.py created |
| 9 | 2026-05-25 | 8-group fix plan: settle.py goals_nl support, supersede logic, monthly fetch windows, inspector/reports switched to live foundation |
| 10 | 2026-05-25 | V3 policy deployed — `V3_ACTIVE` cells (9), goals_nl + corners_nl + dnb + alpha_win |
| 11 | 2026-05-26 | First V3 settlement: 36 picks (22W 8L 6V) — goals_nl 85.7%, corners_nl 87.5%, DNB 6 voids |
| 12 | 2026-05-26 | Project 2 calibration complete — breakeven_odds per cell, alpha_win T1 = HOLD (EV+) |
| 13 | 2026-05-26 | Scheduler activated — first 5 Task Scheduler jobs |
| 14 | 2026-05-26 | League migration analysis (Americas/Asia) — 17,403 fixture backtest |
| 15 | 2026-05-27 | Process audit M1/M2/M3 — corners_nl settlement at API layer, refresh_odds for 8h horizon, dawn-SA catch-up |
| 16 | 2026-05-27 | Hit-rate methodology — restored V3 non-loss convention (voids count as wins) |
| 17 | 2026-05-27 | DF-aware enhanced analysis — DF separates picks 22–26pp on alpha_win, 12.6pp on threeway |
| 18 | 2026-05-27 | **V3.1 live** — 20-cell partition (zone × DF × bts_pocket); scheduler expanded to 12 jobs; `min_n` lowered 50→45 to include `one_sided:DF2:strong_under` |
| 19 | 2026-05-28 | Wide audit + doc-drift sweep — CLAUDE.md, all context docs, engine_knowledge, plan_group1-3, SPA, cron card aligned to V3.1 |
