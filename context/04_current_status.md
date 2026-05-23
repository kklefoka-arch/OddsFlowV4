# Current Status — OddsFlow (as of 2026-05-23)

Update this file at the end of every session.

---

## V3 — OddsFlowV3 (Port 8083)

### State: Running ✅

| Item | Detail |
|------|--------|
| URL (local) | http://localhost:8083 |
| ngrok tunnel | https://steadier-legwarmer-finlike.ngrok-free.dev |
| DB | `data/oddsflow_v3.db` |
| Upcoming fixtures | 1,694 (post-fetch 2026-05-23) |
| Leagues loaded | 30 (all with sportmonks_id set) |
| GitHub | github.com/kklefoka-arch/OddsFlowV3.git — up to date |

### Pages
| Page | URL |
|------|-----|
| Fixtures | http://localhost:8083/fixtures |
| Foundation Matrix | http://localhost:8083/foundation |
| Picks | http://localhost:8083/picks |
| Ingest | http://localhost:8083/ingest |
| Inspector | http://localhost:8083/inspector |
| Health | http://localhost:8083/health |

### What's promoted (as of last check)
- 25 picks in promoted cells
- standard x16, strong x6, one_sided x3
- DNB x22, Alpha Win x3

---

## V2.2 — OddsFlow2 (Port 8082)

### State: Running ✅

| Item | Detail |
|------|--------|
| URL (local) | http://localhost:8082 |
| Branch | `master` — V2.2 canonical |
| GitHub | github.com/kklefoka-arch/oddsflow-v2.git — up to date |
| Tests | 208 passing |

### Extra endpoints V2 has that V3 doesn't yet
| Endpoint | Purpose |
|----------|---------|
| `GET /picks/prx9` | PRX9 premium ranker |
| `POST /admin/corners/backfill` | Patch settled fixtures missing corner scores |
| `GET /diagnostics/today_summary` | Engine perf, fixtures settled, emit settled |

---

## Pending items (carry to next session)

| Item | Priority | Notes |
|------|----------|-------|
| Saudi Arabia Division 1 ID | Medium | Look up in Sportmonks, add to T2 in both `update_leagues.py` and `fetch_upcoming.py` |
| Run V3 engine testing report | Medium | `python scripts/v3_full_report.py` |
| Push V2 commits | Low | 15 commits ahead of remote after CLAUDE.md update |
| V3 `fetch_upcoming.py` daily schedule | Medium | Needs odds closer to match day (48-72h out) |
| PRX9 layer on V3 | Low | Port from V2 when V3 promotion is stable |

---

## How to start both apps

```powershell
# V3
Set-Location C:\OddsFlowV3
uvicorn app.main:app --port 8083 --reload

# V2
Set-Location C:\OddsFlow2\engine
uvicorn app.main:app --port 8082 --reload
```

## How to refresh fixtures

```powershell
Set-Location C:\OddsFlowV3
python fetch_upcoming.py
```

Run this daily — Sportmonks publishes pre-match odds 48-72h before kick-off.
