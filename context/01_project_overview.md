# OddsFlow V4 — Project Overview

**What it is:** Football betting analytics engine for personal use.
Ingests pre-match fixtures and odds from Sportmonks, classifies each match
into a **(draw_zone × BTS pocket)** cell, and surfaces picks for the 9 cells
in the V3 static policy. The structured edge lives in the partition — the
parent combination of `draw_odd × bts_parent` is where hit rates concentrate.

**Who:** Katlego (KK) — sole operator. Single-user system.

**One project. One folder. One repo. One DB.**

---

## How it works (plain language)

1. **Data in** — `fetch_upcoming.py` pulls upcoming fixtures with odds (1X2, BTTS, goals_over_15/25/35, corners_over_75/85/95) from Sportmonks daily. Intraday refresh via `refresh_odds.py`.
2. **Classify** — Each fixture gets a draw zone (4 active zones — strong / standard / low / one_sided) and a BTS pocket (4 — strong_over / slight_over / slight_under / strong_under).
3. **V3 policy** — 9 promoted cells locked from 28,425-fixture analysis. Stored in `app/engine/static_policy.py::V3_ACTIVE`.
4. **Pick output** — Per cell:
   - `goals_nl` (Over 1.5 Goals) — strong + standard
   - `corners_nl` (Over 8.5 Corners) — standard only
   - `dnb` (alpha team — win or draw) — low
   - `alpha_win` (favourite outright) — one_sided
5. **Settle** — `fetch_results.py` writes scores + corners; `settle.py` resolves picks into pick_results (WIN / VOID / LOSS). Hit rate uses V3 non-loss convention.

---

## Key decisions

- **V4 is the only version.** V2.2 and earlier are retired and archived.
- **V3 (Session 11 baseline) is the active policy.** Restored in Session 19 after the V3.1 DF-aware partition drift was reverted. 9 cells, 2-key `(zone, bts_pocket)`.
- **Zone boundaries are the raw-notes overlay** (Session 19): excluded < 2.90, strong 2.90–3.30, standard 3.30–3.80, low 3.80–4.30, one_sided ≥ 4.30. The prior V3 cutoffs let one_sided fixtures bleed into low.
- **All four markets are active in V4.** goals_nl, corners_nl, dnb, alpha_win.
- **No DF as partition. No EV gates. No economic models in the live engine.** These are durable rules — see CLAUDE.md → Durable rules.
- **SQLite, no external services.** Deploy target Railway; runs locally on port 8083.

---

## Technology stack

- **Backend:** Python + FastAPI (uvicorn)
- **Database:** SQLite (`data/oddsflow_v4.db`)
- **Frontend:** SPA — Jinja2 + vanilla JS
- **Deploy target:** Railway (`Procfile`, `railway.toml`)
- **Odds source:** Sportmonks API v3

---

## Reference docs in this folder

| File | Contents |
|------|----------|
| `02_league_config.md` | 30 subscribed leagues, tier assignments |
| `03_engine_rules.md` | Classification, V3 cells, market rules, boundary overlay |
| `04_current_status.md` | Current state, known issues, session log |
| `05_architecture.md` | File map, process flow, API routes, DB tables |
| `06_process_flow.md` | Full fixture lifecycle |
| `07_system_language.md` | Every term defined |
| `engine_knowledge.md` | Tabs + abbreviations + operating notes |
