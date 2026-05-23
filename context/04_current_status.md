# Current Status — OddsFlow V4

Update this file at the end of every session.
Last updated: 2026-05-24 (Session 6)

---

## State: Running ✅

| Item | Detail |
|------|--------|
| Folder | `C:\OddsFlowV4` |
| Port | 8083 (local) |
| ngrok | https://steadier-legwarmer-finlike.ngrok-free.dev |
| DB | `data/oddsflow_v4.db` |
| GitHub | `github.com/kklefoka-arch/OddsFlowV4` |
| Picks today (1d)  | 149 picks — 138 dnb, 11 alpha_win |
| Upcoming fixtures | 3,037 upcoming |
| DB total fixtures | 31,644 (28,607 settled, 3,037 upcoming) |
| draw_zone filled  | 28,710 fixtures with draw_zone + bts_pocket stored |
| emit_log | 207 (all PENDING — upcoming only, no settled emits yet) |

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
| 1 | July–Aug and Sep–Oct fetch windows hit 20-page cap (1,000 fixtures each) | Increase max_pages or use sub-window approach |
| 2 | Cron not yet configured | Run `setup_scheduler.ps1` as admin to register tasks; or use `run_daily.ps1` manually |
| 3 | pick_results = 0 — no post-match settlement yet | Run `python settle.py` after matches complete |

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
