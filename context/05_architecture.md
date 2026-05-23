# OddsFlow V4 — Architecture & File Map

## Process flow
```
Sportmonks API (v3/football/fixtures/between/{start}/{end})
  └─ fetch_upcoming.py  ← run daily
       └─ fixtures table (draw_odd, home_odd, away_odd, btts_yes/no_odd)
            └─ classify_fixture()  [app/engine/classify.py]
                 ├─ zone_of(draw_odd)      → draw_zone [strong|standard|low|one_sided|NULL]
                 └─ bts_of(yes, no)        → bts_pocket [strong_over|slight_over|strong_under|slight_under|NULL]
                      └─ PROMOTED_CELLS lookup  [app/engine/static_policy.py]
                           └─ pick emitted (DNB or Alpha Win)
                                └─ emit_log  INSERT OR IGNORE on pick_uuid  (idempotent)
                                     └─ pick_result when match settles  (/api/fixtures/settle/{id})
```

## File map — `C:\OddsFlowV4`
```
app/
├── main.py                    FastAPI entry — SPA at /, registers all routers
├── settings.py                DATABASE_URL (→ data/oddsflow_v4.db), APP_ENV, LOG_LEVEL
├── api/
│   ├── routes_health.py       GET /health
│   ├── routes_fixtures.py     GET /fixtures (HTML) + /api/fixtures (JSON) + settle
│   ├── routes_foundation.py   GET /foundation — Foundation Matrix page
│   ├── routes_ingest.py       POST /ingest/* — Sportmonks ingest
│   ├── routes_picks.py        GET /picks — stone policy picks + emit_log write
│   ├── routes_upcoming.py     GET /upcoming — fixtures with PROMOTE chips
│   ├── routes_analysis.py     GET /analysis/* — calibration from settled fixtures
│   ├── routes_reports.py      GET /reports/* — emit performance windows
│   ├── routes_inspector.py    GET /inspector/* — partition drift vs stone policy
│   └── routes_diagnostics.py  GET /diagnostics/* + /healthz/deep
├── engine/
│   ├── classify.py            zone_of(), bts_of(), classify_fixture()
│   ├── static_policy.py       PROMOTED_CELLS — 10 cells, stone policy (locked)
│   ├── promotion.py           compute_foundation() — hit rates + promotion logic
│   └── foundation.py          Foundation Matrix builder
├── db/
│   ├── database.py            init_db() + migrations + get_conn()
│   └── schema.sql             Full schema (leagues, teams, fixtures, emit_log, pick_results)
└── frontend/
    ├── templates/engine_view.html  V4 SPA (7 tabs)
    └── static/
        ├── engine.js          SPA JavaScript
        └── engine.css         SPA stylesheet

data/
├── oddsflow_v4.db             Live SQLite DB (not in git)
└── v1_calibration_readonly.db Historical 28k fixtures — engine report reference (not in git)

fetch_upcoming.py              Fetch all 30 leagues from Sportmonks — run daily
scripts/
├── v3_full_report.py          Engine testing report (Phases 2-7) vs calibration DB
├── update_leagues.py          Upsert 30 leagues into leagues table (run to fix blank names)
└── seed_from_calibration.py   One-time seed of V4 DB from calibration DB
archive/                       Zipped retired projects (OddsFlow2, KK_way, original, relaunch)
context/                       Session reference docs (this folder)
CLAUDE.md                      Session entry point — read first, update on close
```

## SPA tabs → API endpoints
| Tab | Endpoint |
|-----|----------|
| Picks | GET /picks?days=N |
| Today | GET /diagnostics/today_summary |
| Upcoming | GET /upcoming?days=N |
| Analysis | GET /analysis/calibration_partition |
| Inspector | GET /inspector/partition_drift |
| Reports | GET /reports/settle_activity |
| Stats | GET /diagnostics/db_state + /odds_coverage |

## DB tables
| Table | Contents |
|-------|----------|
| `leagues` | 30 subscribed leagues with sportmonks_id and tier |
| `teams` | Teams auto-added during fixture fetch |
| `fixtures` | All fixtures — upcoming (home_score IS NULL) and settled |
| `fixture_stats` | Corner/tackle/card stats for settled fixtures |
| `emit_log` | Every pick emitted — UUID, market, pick, odd, zone, bts_pocket |
| `pick_results` | Settlement outcomes (WIN/LOSS/VOID) |
