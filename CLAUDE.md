# OddsFlow V4 — Project orientation

Read this file at the start of every session. It is the single source of truth for V4.
**Update this file at the start, during, and at the end of every session, then commit and push.**
Human-readable context docs are in `context/` — update `context/04_current_status.md` each session.

---

## What this project is

OddsFlow V4 is the unified production football betting analytics engine.
It ingests fixtures + odds from Sportmonks, classifies each fixture into
a (zone × bts_pocket) cell, and emits picks for 10 PROMOTED_CELLS (stone policy).
All picks fire `dnb` (strong/standard zones) or `alpha_win` (one_sided zone).
No goals/corners markets in V4.

Operator: Katlego (KK). Single-user system. Port 8083 locally.
Remote: `github.com/kklefoka-arch/OddsFlowV3.git`
Deploy target: Railway (Procfile + railway.toml present).
ngrok tunnel: `https://steadier-legwarmer-finlike.ngrok-free.dev` → port 8083.

V2.2 (port 8082) is retired as a reference — V4 supersedes it entirely.

---

## Current state (as of 2026-05-23)

- 7 commits on `master`, pushed to GitHub
- V4 SPA live: Picks / Today / Upcoming / Analysis / Inspector / Reports / Stats tabs
- 1694 upcoming fixtures refreshed via fetch_upcoming.py (2026-05-23 run)
- Static stone policy: 10 PROMOTED_CELLS (strong x3, standard x4, one_sided x3)
- emit_log written idempotently via `picks?write=1` or `/picks` (auto-write on load)
- pick_results written when fixture settled via `/api/fixtures/settle/{id}`

**Upcoming fixture query rule** (all queries use):
`home_score IS NULL AND date >= date('now')`

---

## Architecture

```
app/
├── main.py                         FastAPI V4 entry — SPA at /, all routers
├── settings.py                     Pydantic-settings (DATABASE_URL, APP_ENV, LOG_LEVEL)
├── api/
│   ├── routes_health.py            GET /health
│   ├── routes_fixtures.py          GET /fixtures (HTML) + /api/fixtures (JSON) + settle
│   ├── routes_foundation.py        GET /foundation (Foundation Matrix HTML)
│   ├── routes_ingest.py            POST /ingest/* (Sportmonks ingest)
│   ├── routes_picks.py             GET /picks — stone policy picks + emit_log write
│   ├── routes_upcoming.py          GET /upcoming — scheduled fixtures with PROMOTE chips
│   ├── routes_analysis.py          GET /analysis/* — calibration from settled fixtures
│   ├── routes_reports.py           GET /reports/* — emit performance windows
│   ├── routes_inspector.py         GET /inspector/* — partition drift vs stone policy
│   └── routes_diagnostics.py       GET /diagnostics/* + /healthz/deep
├── engine/
│   ├── classify.py                 zone_of(), bts_of(), classify_fixture()
│   ├── natural_lines.py            HALF_LINES — natural/system lines per zone/market
│   ├── promotion.py                compute_foundation() — hit rates + promotion logic
│   ├── foundation.py               Foundation Matrix builder
│   └── static_policy.py            PROMOTED_CELLS stone policy (10 cells, locked)
├── db/
│   ├── database.py                 SQLite connection + init_db() + migrations
│   └── schema.sql                  Full schema (leagues, teams, fixtures, emit_log,
│                                   pick_results, system_health)
└── frontend/
    ├── templates/engine_view.html  V4 SPA (Picks default tab)
    └── static/
        ├── engine.js               V4 SPA JavaScript
        └── engine.css              V4 SPA stylesheet

data/oddsflow_v3.db                 SQLite database (not in git)
fetch_upcoming.py                   Run daily — refreshes pre-match odds from Sportmonks
scripts/v3_full_report.py           Engine testing report (Phases 2-7)
```

---

## Engine constants (locked)

### Draw zones (`zone_of`)
| Zone | Range |
|------|-------|
| `strong` | 2.70 ≤ draw_odd < 3.40 |
| `standard` | 3.40 ≤ draw_odd < 4.10 |
| `low` | 4.10 ≤ draw_odd < 4.80 |
| `one_sided` | draw_odd ≥ 4.80 |
| NULL (excluded) | draw_odd < 2.70 |

### BTS pockets (`bts_of`) — threshold 1.50
| Pocket | Condition |
|--------|-----------|
| `strong_over` | yes favoured AND yes_odd < 1.50 |
| `slight_over` | yes favoured AND yes_odd ≥ 1.50 |
| `strong_under` | no favoured AND no_odd < 1.50 |
| `slight_under` | no favoured AND no_odd ≥ 1.50 |

"Yes favoured" = yes_odd ≤ no_odd.

### Half-lines (natural / system)
| Zone | Goals | Corners |
|------|-------|---------|
| strong / standard | 1.5 / 2.5 | 7.5 / 8.5 |
| low / one_sided | 2.5 / 3.5 | 8.5 / 9.5 |

### Promotion thresholds
| Constant | Value |
|----------|-------|
| `PROMOTE_THRESHOLD` | 72.0% |
| `PROMOTE_LOWER` (tolerance band) | 67.5% |
| `DROP_SECONDARY_GAP` | 4.5 pp |
| `LOW_ZONE_SUPPRESS` | True (low zone → MEASURING, not PROMOTE) |

### 3-way pick logic
- `strong` / `standard` → DNB (alpha win OR draw)
- `low` / `one_sided` → Alpha Win outright only

---

## League tier config

Run `fetch_upcoming.py` daily — Sportmonks publishes pre-match odds 48-72h out.
All 30 subscribed leagues are configured in `fetch_upcoming.py::ACTIVE_LEAGUES`.

| Tier | Count | Leagues |
|------|-------|---------|
| T1 | 13 | PL (8), Ligue 1 (301), La Liga (564), Serie A (384), Allsvenskan (573), Eliteserien (444), Iceland (345), Veikkausliiga (292), Ireland (360), MLS (779), Brazil Serie A (648), J1 (3537), K League 1 (1034) |
| T2 | 14 | La Liga 2 (567), Superettan (579), Ettan N (585), Ettan S (588), Copa Colombia (681), Primera B (678), Ecuador (696), Canada (1689), Ykköseliga (295), Estonia (286, 289), USL Championship (791), J2/J3 (3550), China (989) |
| T3 | 3 | USL League One (1607), MLS Next Pro (2545), Bolivia (1098) |

Note: `max_pages=10` cap (500 rows/window) may truncate large windows — bump if fixtures go missing.

---

## Upcoming fixture query rule

**Always use:**
```sql
WHERE home_score IS NULL AND date >= date('now')
```
**Never use** `status = 'scheduled'` — that column is unreliable.

---

## Project principles

1. **Drop, don't park.** Retired concepts are traced end-to-end and removed.
   Dead code compounds debt.
2. **Process-chart discipline.** Every change examined across the full pipeline:
   `ingest → classify → foundation → picks → emit_log → settle`.
3. **Surface, don't bury.** Critical numbers belong on the operator view,
   not hidden behind separate endpoints.
4. **No schema drift.** Schema lives in `schema.sql`. Migrations run via the
   idempotent migration runner in `database.py`.

---

## Skills registered globally

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `graphify` | `/graphify` | Build knowledge graph from any folder of files |

No other plugins enabled.

---

## Pending next session

- `fetch_upcoming.py` — run manually each morning (or schedule via Task Scheduler)
- Remove stale tracked `__pycache__/*.pyc` files via `git rm --cached -r app/**/__pycache__`
- Bump `max_pages` in `fetch_upcoming.py` (currently 10) if fixtures appear truncated
