# OddsFlow V4 — Project Overview

**What it is:** Football betting analytics engine for personal use.
Ingests fixtures + odds from Sportmonks, classifies each match into a (zone × BTS) cell,
and surfaces picks for cells with strong historical hit rates.

**Who:** Katlego (KK) — sole operator. Single-user system.

**One project. One folder. One repo. One DB.**

---

## How it works (plain language)

1. **Data in** — `fetch_upcoming.py` pulls upcoming fixtures with odds from Sportmonks API
2. **Classify** — Each fixture gets a draw zone (4 options) and a BTS pocket (4 options)
3. **Stone policy** — 10 promoted cells (locked from historical analysis) determine which fixtures get picks
4. **Pick output** — DNB for strong/standard zones, Alpha Win for one_sided zone
5. **Settle** — When a match ends, `/api/fixtures/settle/{id}` records the result

---

## Key decisions

- **V4 is the only version** — V2.2 and all prior engines are retired and archived
- **Stone policy** — The 10 promoted cells are locked from 28,425 settled fixtures. They do not change with local DB state.
- **No goals/corners picks in V4** — Only DNB and Alpha Win markets fire
- **SQLite, no external services** — Deploy target is Railway; runs locally on port 8083

---

## Technology stack

- **Backend:** Python + FastAPI (uvicorn)
- **Database:** SQLite (`data/oddsflow_v4.db`)
- **Frontend:** Single-Page App — Jinja2 template + vanilla JS (no framework)
- **Deploy target:** Railway (Procfile + railway.toml)
- **Odds source:** Sportmonks API v3

---

## Reference docs in this folder

| File | Contents |
|------|----------|
| `02_league_config.md` | 30 subscribed leagues, tier assignments |
| `03_engine_rules.md` | Classification logic, promotion thresholds |
| `04_current_status.md` | Current state, known issues, next steps |
| `05_architecture.md` | File map, process flow, API route table |
