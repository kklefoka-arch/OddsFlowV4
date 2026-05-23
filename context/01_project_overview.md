# OddsFlow — Project Overview

**What it is:** A football betting analytics engine built for personal use.
It ingests fixtures and odds from Sportmonks, classifies each match into a cell,
and surfaces picks for cells that have historically performed well.

**Who built it:** Katlego (KK) — BTech Systems Engineering.

---

## Two versions running simultaneously

| Version | Port | Purpose | Path |
|---------|------|---------|------|
| **V3** | 8083 | Clean production engine | `C:\OddsFlowV3` |
| **V2.2** | 8082 | Reference engine (battle-tested, PRX9 layer) | `C:\OddsFlow2` |

Both run locally. V3 is the future; V2.2 is kept for signal validation.

---

## How it works (plain language)

1. **Data in** — Sportmonks API provides upcoming fixtures with odds (1X2, BTTS, corners, goals)
2. **Classify** — Each fixture is placed into a "cell" based on:
   - **Draw zone** — how strong the draw odd is (4 zones: strong / standard / low / one_sided)
   - **BTS pocket** — which way the BTTS market leans (4 pockets: strong_over / slight_over / slight_under / strong_under)
3. **Foundation Matrix** — Settled historical fixtures fill a grid. Each cell shows hit rates (how often "over" wins, etc.)
4. **Promotion** — Cells that hit ≥72% are promoted. Picks for promoted cells are surfaced.
5. **Pick output** — Fixtures in promoted cells get picks: goals line, corners line, or DNB/Alpha Win

---

## Data source

- **Provider:** Sportmonks (`api.sportmonks.com/v3/football`)
- **30 leagues** subscribed — 13 T1, 14 T2, 3 T3 (see `02_league_config.md`)
- **Run `fetch_upcoming.py` daily** — odds are published 48-72h before kick-off

---

## Technology stack

- **Backend:** Python + FastAPI
- **Database:** SQLite (`data/oddsflow_v3.db`)
- **Templates:** Jinja2 HTML (operator-facing UI)
- **No frontend framework** — plain HTML/CSS/JS
- **Deploy target:** Railway (Procfile + railway.toml present)

---

## Status as of 2026-05-23

- V3: 1,694 upcoming fixtures loaded across 30 leagues
- V3: Picks live in promoted cells (goals, corners, DNB, Alpha Win)
- V2: 14 commits ahead of remote, all tests passing (208 tests)
- Both apps running locally — V3 on :8083, V2 on :8082
