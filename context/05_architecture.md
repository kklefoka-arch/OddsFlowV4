# OddsFlow V4 — Architecture & File Map

## Process flow

```
Sportmonks API (v3/football/fixtures/between/{start}/{end})
  └─ fetch_upcoming.py  (daily 08:00 SAST)         [+ refresh_odds.py @ 14:30 SAST]
       └─ fixtures table (1X2, BTTS, goals_over_*_odd, corners_over_*_odd, kickoff_utc)
            └─ classify_fixture()  [app/engine/classify.py]
                 ├─ zone_of(draw_odd)       → strong | standard | low | one_sided | NULL
                 ├─ df_of(home, away)       → DF0 | DF1 | DF2
                 └─ bts_of(yes, no)         → strong_over | slight_over | slight_under | strong_under | NULL
                      └─ V3_ACTIVE lookup  [app/engine/static_policy.py]
                           └─ per-market pick(s): goals_nl | corners_nl | dnb | alpha_win
                                └─ emit_log  (INSERT OR IGNORE on pick_uuid; supersede stale)

Sportmonks API (results)
  └─ fetch_results.py  (after match windows close — 23:30, 03:00, 06:00 SAST)
       ├─ fixtures.home_score / away_score / total_goals
       └─ fixture_stats.home_corners / away_corners / total_corners
            └─ settle.py  (23:45 / 03:15 / 06:15 SAST)
                 └─ pick_results  (outcome, actual_value)
                      └─ Inspector + Reports tabs surface settled performance
```

## File map — `C:\OddsFlowV4`

```
app/
├── main.py                    FastAPI entry — SPA at /, registers all routers
├── settings.py                DATABASE_URL (→ data/oddsflow_v4.db), APP_ENV, LOG_LEVEL
├── api/
│   ├── routes_health.py         GET /health
│   ├── routes_fixtures.py       /fixtures HTML + /api/fixtures JSON + settle helpers
│   ├── routes_foundation.py     GET /foundation (HTML) + /api/foundation (matrix JSON)
│   ├── routes_ingest.py         POST /ingest/* — Sportmonks ingest helpers
│   ├── routes_picks.py          GET /picks — V3.1 policy lookup + emit_log write + drift
│   ├── routes_upcoming.py       GET /upcoming — fixtures with V3.1 cell chips
│   ├── routes_reports.py        /reports/* — emit performance, recent, settle activity, market breakdown
│   ├── routes_inspector.py      /inspector/* — partition_drift, recent_settled, similar, daily_calendar
│   ├── routes_diagnostics.py    /diagnostics/* + multi-metric cron heartbeat
│   └── routes_results.py        /api/results + /api/livescores (livescores polling)
├── engine/
│   ├── classify.py              zone_of(), bts_of(), df_of(), classify_fixture()
│   ├── static_policy.py         V3_ACTIVE / V3_MARKETS / PROMOTED_CELLS — authoritative live policy
│   ├── promotion.py             compute_foundation() — display matrix only (low cells = MEASURING)
│   ├── foundation.py            load_foundation(conn) — settled-fixture loader
│   └── natural_lines.py         natural_line(zone, market), system_line(zone, market)
├── db/
│   ├── database.py              init_db() + get_conn()
│   └── schema.sql               Full schema
└── frontend/
    ├── templates/engine_view.html  V4 SPA (8 tabs incl. Results)
    └── static/
        ├── engine.js
        └── engine.css

data/
├── oddsflow_v4.db                 Live SQLite DB (not in git)
└── v1_calibration_readonly.db     Historical 28k fixtures (not in git)

fetch_upcoming.py                  Daily fetch — odds + kickoff datetimes
emit_picks.py                      Calls /picks?days=3 + heartbeat
refresh_odds.py                    Intraday odds refresh for next-8h fixtures (M2)
refresh_stats.py                   Corner-stats backfill (14d lookback, M3)
fetch_results.py                   Scores + corner stats post-match
settle.py                          pick_results writer
run_daily.ps1                      Operator chained pipeline
setup_scheduler.ps1                Registers 12 Task Scheduler jobs
scripts/
├── update_leagues.py              Upsert 30 leagues
├── seed_from_calibration.py       One-time seed from calibration DB
├── league_migration_analysis.py   Writes Excel/JSON to "OddsFlow AI Website/Output"
└── v3_full_report.py              Engine testing report
archive/                           Zipped retired projects
context/                           This folder
CLAUDE.md                          Session entry point
```

## SPA tabs → API endpoints

| Tab | Endpoint(s) |
|-----|-------------|
| Picks | `GET /picks?days=N` |
| Today | `GET /diagnostics/today_summary` |
| Upcoming | `GET /upcoming?days=N&tier=T` |
| Analysis | `GET /api/foundation` |
| Inspector | `GET /inspector/partition_drift` + `/recent_settled` + `/similar` + `/daily_calendar` |
| Reports | `GET /reports/settle_activity` + `/emit_performance` + `/emit_recent` + `/emit_market_breakdown` |
| Stats | `GET /diagnostics/db_state` + `/odds_coverage` + `/cron/heartbeat` + `/drift_report` + `/activity_by_tier` |
| Results | `GET /api/results` + `/api/livescores` |

## DB tables

| Table | Contents |
|-------|----------|
| `leagues` | Subscribed + historical leagues with `sportmonks_id` and `tier` |
| `teams` | Teams auto-added during fixture fetch |
| `fixtures` | All fixtures — upcoming and settled. Odds: `home_odd`, `draw_odd`, `away_odd`, `btts_yes_odd`, `btts_no_odd`, `goals_over_15/25/35_odd`, `corners_over_75/85/95_odd` |
| `fixture_stats` | Corner stats + other per-match stats for settled fixtures |
| `emit_log` | Every pick emitted — `pick_uuid`, market, pick label, pick_odd, zone/bts/(df via cell key) |
| `pick_results` | Settlement outcomes (WIN/VOID/LOSS string + 1.0/0.5/0.0 float) |
| `system_health` | Per-task heartbeats (`fetch_upcoming`, `fetch_results`, `settle`, `emit_picks`, `refresh_odds`, `refresh_stats`, plus legacy `cron_heartbeat`) |
| `h2h_meetings` | Head-to-head meeting history (~58k rows) |
