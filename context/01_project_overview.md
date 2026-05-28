# OddsFlow V4 — Project Overview

**What it is:** Football betting analytics engine for personal use.
Ingests pre-match fixtures and odds from Sportmonks, classifies each match into a
(draw_zone × DF × BTS pocket) cell, and emits picks for the 20 cells in the active
V3.1 policy.

**Who:** Katlego (KK) — sole operator. Single-user system.

**One project. One folder. One repo. One DB.**

---

## How it works (plain language)

1. **Data in** — `fetch_upcoming.py` pulls upcoming fixtures with odds (1X2, BTTS, goals_over_15/25/35, corners_over_75/85/95) from Sportmonks. Daily; intraday top-up via `refresh_odds.py`.
2. **Classify** — Each fixture gets a draw zone (4 options), a DF tier (DF0/DF1/DF2 — rounded `|home_odd − away_odd|`), and a BTS pocket (4 options).
3. **V3.1 policy** — 20 promoted cells (locked from 28,425-fixture analysis) determine which fixtures and which markets fire. Stored in `app/engine/static_policy.py::V3_ACTIVE`.
4. **Pick output** — Per cell:
   - `goals_nl` (Over 1.5 Goals) for strong + standard
   - `corners_nl` (Over 8.5 Corners) for standard only
   - `dnb` (alpha team — win or draw) for low
   - `alpha_win` (favourite outright) for one_sided
5. **Settle** — After matches, `fetch_results.py` writes scores and corner stats; `settle.py` resolves each pending emit into pick_results (WIN / VOID / LOSS).

---

## Key decisions

- **V4 is the only version.** V2.2 and earlier are retired and archived.
- **V3.1 policy is static and pre-computed.** The 20 cells come from 28,425 settled fixtures plus the 2026-05-27 DF separation analysis. They do not change with local DB state.
- **All four markets are active in V4** — `goals_nl`, `corners_nl`, `dnb`, `alpha_win`. The old "no goals/corners picks in V4" decision was rolled back when goals_nl was added in Session 7 and corners_nl in Session 10/11.
- **Low zone is active** — `LOW_ZONE_SUPPRESS = False` in `static_policy.py`. Foundation-matrix *display* still marks low cells `MEASURING` via `promotion.py`, by design.
- **SQLite, no external services.** Deploy target is Railway; runs locally on port 8083.

---

## Technology stack

- **Backend:** Python + FastAPI (uvicorn)
- **Database:** SQLite (`data/oddsflow_v4.db`)
- **Frontend:** Single-Page App — Jinja2 template + vanilla JS (no framework)
- **Deploy target:** Railway (`Procfile`, `railway.toml`)
- **Odds source:** Sportmonks API v3

---

## Reference docs in this folder

| File | Contents |
|------|----------|
| `02_league_config.md` | 30 subscribed leagues, tier assignments |
| `03_engine_rules.md` | Classification logic (zone × DF × bts), V3.1 cells, market rules |
| `04_current_status.md` | Current state, known issues, session log |
| `05_architecture.md` | File map, process flow, API routes, DB tables |
| `06_process_flow.md` | Full fixture lifecycle, every phase, every table |
| `07_system_language.md` | Every term defined — what exists, what does not |
| `engine_knowledge.md` | SPA tabs + abbreviations + operating notes |
