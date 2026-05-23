# OddsFlow V3 — Project orientation

Read this file at the start of every session. It is the single source of truth for V3.
**Update this file at the start, during, and at the end of every session, then commit and push.**
Human-readable context docs are in `context/` — update `context/04_current_status.md` each session.

---

## What this project is

OddsFlow V3 is the clean production football betting analytics engine.
It ingests fixtures + odds from Sportmonks, classifies each fixture into
a (zone × bts_pocket) cell, and emits picks for promoted cells.

Operator: Katlego (KK). Single-user system. Port 8083 locally.
Remote: `github.com/kklefoka-arch/OddsFlowV3.git` (nothing pushed yet as of 2026-05-23).
Deploy target: Railway (Procfile + railway.toml present).
ngrok tunnel: `https://steadier-legwarmer-finlike.ngrok-free.dev` → port 8083.

V2.2 (port 8082) runs in parallel as the reference engine — see `C:\OddsFlow2\CLAUDE.md`.

---

## Current state (as of 2026-05-23)

- 5 commits on `master`, **none pushed to GitHub**
- 412 upcoming fixtures loaded (MLS 779, Ireland 360, PL 8)
- 25 picks live in promoted cells (standard x16, strong x6, one_sided x3; DNB x22, Alpha Win x3)
- Uncommitted source changes: `routes_fixtures.py`, `routes_ingest.py`, `routes_picks.py`, `fixtures.html`
- Untracked: `static_policy.py`, `fetch_upcoming.py` — need staging and commit

**Upcoming fixture status bug (fixed 2026-05-22):** all upcoming queries now use
`home_score IS NULL AND date >= date('now')`, not `status='scheduled'`. Applied across
`routes_fixtures.py`, `routes_picks.py`, `routes_ingest.py`.

---

## Architecture

```
app/
├── main.py                         FastAPI app entry point + lifespan
├── settings.py                     Pydantic-settings (DATABASE_URL, APP_ENV, LOG_LEVEL)
├── api/
│   ├── routes_health.py            GET /healthz
│   ├── routes_fixtures.py          GET /fixtures/upcoming
│   ├── routes_foundation.py        GET /foundation (Foundation Matrix)
│   ├── routes_ingest.py            POST /ingest/* (Sportmonks ingest)
│   ├── routes_inspector.py         GET /inspector/*
│   └── routes_picks.py             GET /picks (promotion-based picks)
├── engine/
│   ├── classify.py                 zone_of(), bts_of(), classify_fixture()
│   ├── natural_lines.py            HALF_LINES — natural/system lines per zone/market
│   ├── promotion.py                compute_foundation() — hit rates + promotion logic
│   ├── foundation.py               Foundation Matrix builder
│   └── static_policy.py            Static zone-market policy (untracked)
├── db/
│   ├── database.py                 SQLite connection + init_db()
│   └── schema.sql                  Full schema (leagues, teams, fixtures, emit_log, etc.)
└── frontend/
    └── templates/                  Jinja2 HTML templates (fixtures, picks, inspector…)

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

- **T1**: 23 leagues (includes Iceland 345, Slovakia 540)
- **T2**: 8 leagues (includes France National 313)
- **T3**: 3 leagues
- Saudi Arabia Division 1 ID unknown — add to T2 when confirmed

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

- Commit and push V3 to GitHub (5 local commits + uncommitted route changes)
- Confirm `static_policy.py` and `fetch_upcoming.py` should be staged
- Run V3 engine testing report (`scripts/v3_full_report.py`)
- Saudi Arabia Division 1 Sportmonks ID — look up and add to T2
- `fetch_upcoming.py` should be scheduled or run manually each morning
