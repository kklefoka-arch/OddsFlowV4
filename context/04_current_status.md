# Current Status — OddsFlow V4

Update this file at the end of every session.
Last updated: 2026-05-23

---

## State: Running ✅

| Item | Detail |
|------|--------|
| Folder | `C:\OddsFlowV4` (renamed from OddsFlowV3 this session) |
| Port | 8083 (local) |
| ngrok | https://steadier-legwarmer-finlike.ngrok-free.dev |
| DB | `data/oddsflow_v4.db` |
| GitHub | `github.com/kklefoka-arch/OddsFlowV4` (renamed this session) |
| Picks (7d window) | 182 picks — 168 dnb, 14 alpha_win — all promote class |
| Upcoming fixtures | 2,404 total; 242 with draw_odd today (Sportmonks: odds 48-72h out) |

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
| 1 | 18 of 30 leagues missing from `leagues` DB table → blank league_name/country in SPA | `python scripts/update_leagues.py` |
| 2 | `fetch_upcoming.py` max_pages=10 cap (500 rows/window) may miss distant fixtures | Bump to `max_pages=20` in fetch_upcoming.py |
| 3 | `/upcoming` tier filter uses `lg.tier` (league JOIN) — broken until issue #1 fixed | Fixed by #1 |

---

## Session log

| Date | Work done |
|------|-----------|
| 2026-05-22 | V4 built — V3 backend + V2 SPA merged, 7 tabs live, 25 picks |
| 2026-05-23 AM | League audit, fetch run (1694 updated), SPA verified, engine report |
| 2026-05-23 PM | Consolidation — renamed V3→V4 folder+repo, archived retired projects, cleaned 6 GitHub repos, restructured context per workflow doc |
