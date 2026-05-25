# Current Status — OddsFlow V4

Update this file at the end of every session.
Last updated: 2026-05-25 (Session 9)

---

## State: Running ✅

| Item | Detail |
|------|--------|
| Folder | `C:\OddsFlowV4` |
| Port | 8083 (local) |
| ngrok | https://steadier-legwarmer-finlike.ngrok-free.dev |
| DB | `data/oddsflow_v4.db` |
| GitHub | `github.com/kklefoka-arch/OddsFlowV4` |
| Picks (7d window) | 392 total — 200 pending, 192 settled (101W 35V 56L = 61.7% hit rate) |
| By market (7d) | dnb: 267 \| goals_nl: 112 (98 with odd, 88%) \| alpha_win: 23 |
| Upcoming fixtures | 3,189 upcoming |
| DB total fixtures | 31,990 (28,801 settled, 3,189 upcoming) |
| emit_log | 392 rows — 192 settled, 200 pending |
| pick_results | 192 (101 WIN, 35 VOID, 56 LOSS) |
| goals_nl lines | Over 2.5 Goals only (effective-line fallback working) |

## How to start
```powershell
Set-Location C:\OddsFlowV4
uvicorn app.main:app --host 0.0.0.0 --port 8083 --reload
```

## How to refresh fixtures (run daily)
```powershell
Set-Location C:\OddsFlowV4
python fetch_upcoming.py
```

---

## Known issues / pending fixes

| # | Issue | Fix |
|---|-------|-----|
| 1 | Cron not yet configured | Run `setup_scheduler.ps1` as Admin to register Windows Task Scheduler jobs |
| 2 | 11 emit_log "duplicate" pairs | Both rows have pick_results — odds flipped mid-session, alpha team changed, both settled. Can't delete. Supersede logic prevents new ones. |
| 3 | drift: 3 cells drifting (one_sided:slight_over, standard:strong_over, strong:slight_over) | Early signal — n=20–39 each. Monitor; don't demote yet. |
| 4 | goals_nl 14 picks with no pick_odd | No o15/o25/o35 quoted by Sportmonks for those fixtures — normal for some leagues |
| 5 | cron_heartbeat shows None | run_daily.ps1 not yet run today — expected |

---

## Session log

| Date | Work done |
|------|-----------|
| 2026-05-22 | V4 built — V3 backend + V2 SPA merged, 7 tabs live, 25 picks |
| 2026-05-23 AM | League audit, fetch run (1694 updated), SPA verified, engine report |
| 2026-05-23 PM | Consolidation — renamed V3→V4 folder+repo, archived retired projects, cleaned 6 GitHub repos, restructured context per workflow doc |
| 2026-05-23 LATE | Pending items cleared. league_id bug fixed (1,984 upcoming fixtures corrected + fetch_upcoming.py patched). Fetch run (1,120 inserted, 1,838 updated). All 7 tabs verified. context/engine_knowledge.md created. |
| 2026-05-23 SESSION 4 | V3 engine fully wired to V4 SPA. Picks now fire from live compute_foundation() (not stone policy). Analysis tab rebuilt with ALL/T1/T2+T3 Foundation Matrix. fetch_upcoming.py stores full kickoff datetimes. PROMOTE/PROMOTE_TOLERANCE constants added to promotion.py. Dead routes_analysis.py removed. OddsFlow2 deleted. 6-agent audit deployed — all clear. 10 cells promoted (28,477 fixtures). Server confirmed healthy. |
| 2026-05-23 SESSION 5 | Zero-based 6-phase system test completed. Issues found and fixed: (1) date filter bug in picks+upcoming routes — `date <= horizon` excluded full-datetime fixtures on horizon day; fixed to `substr(date,1,10) <= horizon`. (2) routes_upcoming.py switched from stone policy (PROMOTED_CELLS) to live foundation. (3) foundation summary.promoted_cells corrected to count threeway-promoted cells only (10, was 11). (4) settle.py script created for settlement pipeline. All fixes verified. Commit pending. |
| 2026-05-24 SESSION 6 | Group gap planning methodology introduced. Three group plans written (plan_group1_display, plan_group2_data_quality, plan_group3_automation). All three groups implemented: Results tab (8th tab) with DB history + livescores in-play + auto-settle hook. Inspector similar-odds history panel (loads on pick card click). Ghost cleanup (1,349 deleted). draw_zone/bts_pocket backfilled (28,669 fixtures). fetch_upcoming.py writes zone/bts on insert/update. run_daily.ps1 + setup_scheduler.ps1 created. system_health heartbeats on all 3 scripts. 9/9 endpoint test passed. |
| 2026-05-24 SESSION 7 | start_server.ps1 created (starts uvicorn + ngrok together). Diagnosed one_sided zone: 3 of 4 cells promoted, actively emitting alpha_win picks (not suppressed). Goals NL picks added — 6 cells promoted (standard:slight_over 78%, standard:strong_over 84%, strong:slight_over 72%, one_sided:slight_over 68%, standard:strong_under 74%, one_sided:strong_over 76%). Engine now emits 3 markets: dnb, alpha_win, goals_nl. 195 picks in 7d window (95 dnb, 90 goals_nl, 10 alpha_win). SPA updated: goals_nl rows on cards, hit rate green tag on all market rows (dnb, alpha_win, goals_nl), Goals NL count in summary strip. |
| 2026-05-24 SESSION 8 | Goals odds fetched from Sportmonks market_id=7 (Goal Line). fetch_upcoming.py now extracts best over-odd for 1.5, 2.5, 3.5 lines and stores in goals_over_15/25/35_odd columns. 2,871 fixtures updated. routes_picks.py uses natural-line odd as pick_odd; falls back to o25 since over 1.5 is rarely quoted by bookmakers. 94/107 goals_nl picks now show a pick_odd. Note: odds displayed for strong/standard zone are Over 2.5 price (fallback) — EV analysis pending. |
| 2026-05-25 SESSION 9 | Full-system audit + 8-group fix plan executed. (1) settle.py: goals_nl settlement added (regex extracts line from pick label). (2) routes_picks.py: effective_line logic — picks use actual quoted line, not always "Over 1.5"; stale NULL-odd "Over 1.5" rows cleaned (121 deleted). (3) write_emit_log() supersede logic: before INSERT, deletes stale unsettled pick for same (fixture,market) if label changed — prevents duplicates. (4) kickoff_today bug fixed (substr match). (5) fetch_upcoming.py: start window uses TODAY dynamically; July–Oct split into monthly windows (max_pages=30). (6) draw_zone/bts_pocket backfill attempted on settled fixtures (all legitimate NULLs — no draw_odd). (7) Inspector + reports switched from static PROMOTED_CELLS to live compute_foundation(). (8) run_daily.ps1 heartbeat added. 189 fixtures scored, 192 picks settled (61.7% hit rate). 11 remaining "duplicates" are protected by pick_results. |
