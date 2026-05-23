# File Map — Where Things Live

Quick reference for navigating both codebases.

---

## V3 — C:\OddsFlowV3

```
app/
├── main.py                         App entry point — registers all routers
├── settings.py                     Env config (DATABASE_URL, APP_ENV, LOG_LEVEL)
│
├── api/
│   ├── routes_health.py            GET /health
│   ├── routes_fixtures.py          GET /fixtures/upcoming
│   ├── routes_foundation.py        GET /foundation  ← Foundation Matrix
│   ├── routes_ingest.py            GET /ingest, POST /api/fixtures/add
│   ├── routes_inspector.py         GET /inspector/*
│   └── routes_picks.py             GET /picks  ← The main pick output
│
├── engine/
│   ├── classify.py                 zone_of(), bts_of()  ← classification logic
│   ├── natural_lines.py            HALF_LINES — which line applies to which zone
│   ├── promotion.py                compute_foundation() — hit rates + PROMOTE logic
│   ├── foundation.py               Foundation Matrix assembly
│   └── static_policy.py            Static zone-market policy
│
├── db/
│   ├── database.py                 init_db(), get_conn()
│   └── schema.sql                  All table definitions
│
└── frontend/
    ├── jinja.py                    Template engine setup
    ├── static/
    │   ├── app.js                  Frontend JS
    │   └── style.css
    └── templates/
        ├── base.html
        ├── fixtures.html           Upcoming fixtures page
        ├── foundation.html         Foundation Matrix page
        ├── picks.html              Picks page
        ├── ingest.html             Manual fixture add
        └── inspector.html          Inspector page

data/
└── oddsflow_v3.db                  SQLite database (not in git)

scripts/
├── update_leagues.py               Upsert all 30 leagues from subscription list
├── seed_from_calibration.py        Seed V3 from V2 calibration DB
└── v3_full_report.py               Engine testing report (Phases 2-7)

context/                            ← You are here — human-readable project docs
fetch_upcoming.py                   Run daily — fetches Sportmonks odds
leagues_no_upcoming.md              Leagues with no upcoming fixtures
CLAUDE.md                           Session entry point for Claude Code
```

---

## V2.2 — C:\OddsFlow2

```
engine/app/
├── config.py                       Zone constants, BTS_V2, MODEL_CUTOFF_AT
│
├── firing/
│   ├── natural_lines.py            Asian whole-line truth
│   └── promote_qualification.py    Wilson lower bound promotion logic
│
├── api/
│   ├── routes_picks.py             /picks + /picks/prx9 (PRX9 premium ranker)
│   ├── routes_diagnostics.py       /diagnostics/* (today_summary, db_state)
│   ├── routes_reports.py           /reports/emit_performance
│   ├── routes_inspector.py         /inspector/* (settled, windows)
│   ├── routes_analysis.py          /analysis/* (calibration, tier stats)
│   ├── routes_fixtures.py          /upcoming
│   └── routes_pipeline.py          /calibration/run (admin)
│
├── pipeline/
│   └── historical_pipeline.py      Fetch + classify historical fixtures
│
├── analytics/
│   ├── partition_stats.py          Legacy 3-tuple aggregator
│   ├── signal_stability.py         Wilson lower bound, Holt-Winters
│   └── snapshot.py                 Stats snapshot writer
│
├── integrity/                      Chain-hash enforcement
└── frontend/static/engine.js       Single-page operator console

docs/
├── engine_constants_reference.md   Locked classifier constants (do not change without ADR)
├── ADR-001 through ADR-004         Why key decisions were made
└── deploy_runbook.md               Railway deploy procedure

CLAUDE.md                           Session entry point for Claude Code
```

---

## Database tables (V3)

| Table | What it holds |
|-------|--------------|
| `leagues` | All 30 subscribed leagues with sportmonks_id and tier |
| `teams` | Teams auto-added during fixture fetch |
| `fixtures` | All fixtures — upcoming (home_score IS NULL) and settled |
| `fixture_stats` | Corner/tackle/card stats for settled fixtures |
| `h2h_meetings` | Head-to-head historical meetings |
| `emit_log` | Every pick emitted — UUID, chain hash, market, line, odds |
| `pick_results` | Settlement outcomes for emitted picks (WIN/LOSS/VOID) |
