# Current Status — OddsFlow V4

Update this file at the end of every session.
Last updated: 2026-05-23

---

## State: Running ✅

| Item | Detail |
|------|--------|
| Folder | `C:\OddsFlowV4` |
| Port | 8083 (local) |
| ngrok | https://steadier-legwarmer-finlike.ngrok-free.dev |
| DB | `data/oddsflow_v4.db` |
| GitHub | `github.com/kklefoka-arch/OddsFlowV4` |
| Picks (3d window) | 170 picks — 157 dnb, 13 alpha_win — all promote class |
| Upcoming fixtures | 4,391 upcoming (391 in 7d window, 184 promoted) |
| DB total fixtures | 32,993 (28,602 settled, 4,391 upcoming) |
| emit_log | 198 (all PENDING — upcoming only, no settled emits yet) |

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
| 2 | Cron never_fired — no scheduled automation | Run `python fetch_upcoming.py` manually daily |
| 3 | pick_results = 0 — no post-match settlement yet | Expected — will populate as upcoming fixtures complete |

---

## Session log

| Date | Work done |
|------|-----------|
| 2026-05-22 | V4 built — V3 backend + V2 SPA merged, 7 tabs live, 25 picks |
| 2026-05-23 AM | League audit, fetch run (1694 updated), SPA verified, engine report |
| 2026-05-23 PM | Consolidation — renamed V3→V4 folder+repo, archived retired projects, cleaned 6 GitHub repos, restructured context per workflow doc |
| 2026-05-23 LATE | Pending items cleared. league_id bug fixed (1,984 upcoming fixtures corrected + fetch_upcoming.py patched). Fetch run (1,120 inserted, 1,838 updated). All 7 tabs verified. context/engine_knowledge.md created. |
