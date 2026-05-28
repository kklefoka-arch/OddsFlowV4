# OddsFlow V4 — Engine Knowledge (V3.1)

> Living document. Updated at the end of each session.
> Last updated: 2026-05-28 (Session 19 — V3.1 doc-drift sweep)

---

## Engine Architecture

OddsFlow V4 is a football betting analytics engine. It ingests pre-match fixtures and odds from the Sportmonks API, classifies each fixture into a `(draw_zone × DF × bts_pocket)` cell, and emits picks for the 20 cells in the active V3.1 policy.

### Process Flow

```
[Sportmonks API]
      |
      | fetch_upcoming.py (daily 08:00 SAST) + refresh_odds.py (intraday 14:30)
      v
[fixtures table]  ←── teams, leagues
      |
      | classify_fixture()
      v
[zone_of(draw_odd)] + [df_of(home, away)] + [bts_of(yes, no)]
      |
      v
[V3_ACTIVE lookup] (static_policy.py — 20 cells)
      |
      ├── cell not active → skip (partition_not_promoted)
      ├── draw_odd missing → skip (unclassifiable)
      └── cell active → one or two markets emit
                         |
                         ├ goals_nl (Over 1.5 Goals)  — strong + standard
                         ├ corners_nl (Over 8.5 Corners) — standard only
                         ├ dnb (alpha-or-draw)        — low
                         └ alpha_win (favourite)      — one_sided
                              |
                         [emit_log table]
                              |
                  pick_uuid = sha256(fixture:market:pick)[:36]
                  write_emit_log() supersedes stale unsettled rows
```

### Key Files

| File | Role |
|------|------|
| `fetch_upcoming.py` | Daily fetch — fixtures + 1X2/BTTS/goals_over_*/corners_over_* odds + kickoff datetimes |
| `emit_picks.py` | Calls `/picks?days=3` + writes `emit_picks` heartbeat |
| `refresh_odds.py` | Intraday odds refresh for next-8h fixtures (M2) |
| `refresh_stats.py` | 14-day corner-stats backfill (M3) |
| `fetch_results.py` | Scores + `fixture_stats` after match windows |
| `settle.py` | Writes `pick_results` (WIN/LOSS/VOID) |
| `app/engine/classify.py` | `zone_of()` + `df_of()` + `bts_of()` |
| `app/engine/static_policy.py` | `V3_ACTIVE` / `V3_MARKETS` / `PROMOTED_CELLS` — authoritative live policy (20 cells) |
| `app/engine/promotion.py` | `compute_foundation()` — display matrix only (low cells `MEASURING`) |
| `app/engine/foundation.py` | `load_foundation(conn)` — settled-fixture loader |
| `app/engine/natural_lines.py` | natural / system line helpers |
| `app/api/routes_picks.py` | `/picks` — V3.1 lookup + emit_log writer + drift |
| `app/api/routes_upcoming.py` | All upcoming fixtures with classification |
| `app/api/routes_foundation.py` | `/foundation` HTML + `/api/foundation` JSON (Analysis tab) |
| `app/api/routes_inspector.py` | partition_drift, recent_settled, similar, daily_calendar |
| `app/api/routes_reports.py` | emit_performance, emit_recent, emit_market_breakdown, settle_activity, paper_trading.csv |
| `app/api/routes_results.py` | `/api/results` + `/api/livescores` (Results tab) |
| `app/api/routes_diagnostics.py` | today_summary, db_state, odds_coverage, cron heartbeat (multi-metric V3.1), drift_report, activity_by_tier |
| `app/db/database.py` | SQLite connection helper |
| `app/settings.py` | Config (DB path, env, log) |
| `app/frontend/templates/engine_view.html` | SPA — 8 tabs |
| `app/frontend/static/engine.js` | Tab logic, fetch calls, rendering |
| `data/oddsflow_v4.db` | Live SQLite DB (not in git) |

### Database Tables

| Table | Purpose |
|-------|---------|
| `fixtures` | Fixture + odds + scores + `draw_zone`, `bts_pocket` (stored from Session 6) |
| `teams` | Team registry |
| `leagues` | League registry + tier |
| `emit_log` | Every pick emitted — idempotent via `pick_uuid` |
| `pick_results` | Settled pick outcomes |
| `system_health` | Heartbeats — `fetch_upcoming`, `fetch_results`, `settle`, `emit_picks`, `refresh_odds`, `refresh_stats`, plus legacy `cron_heartbeat` |
| `fixture_stats` | Corners + match stats |
| `h2h_meetings` | Head-to-head history (~58k rows, reserved for Project 3) |

---

## Classification (three axes)

### Draw Zone (`zone_of(draw_odd)`)

| Zone | Draw odd range | Market routed |
|------|----------------|---------------|
| `strong` | 2.70 ≤ odd < 3.40 | goals_nl |
| `standard` | 3.40 ≤ odd < 4.10 | goals_nl + corners_nl |
| `low` | 4.10 ≤ odd < 4.80 | dnb (ACTIVE — `LOW_ZONE_SUPPRESS = False`) |
| `one_sided` | odd ≥ 4.80 | alpha_win |
| *(excluded)* | odd < 2.70 | Not classified |

### DF (`df_of(home_odd, away_odd)`) — V3.1 axis

| DF | Condition |
|----|-----------|
| `DF0` | rounded diff < 0.5 |
| `DF1` | 0.5 ≤ rounded diff < 1.5 |
| `DF2` | rounded diff ≥ 1.5 |

### BTS Pocket (`bts_of(yes, no)`)

| Pocket | Condition |
|--------|-----------|
| `strong_over` | Yes favoured AND `yes_odd < 1.50` |
| `slight_over` | Yes favoured AND `yes_odd ≥ 1.50` |
| `strong_under` | No favoured AND `no_odd < 1.50` |
| `slight_under` | No favoured AND `no_odd ≥ 1.50` |

### Partition Key
`zone:DF:bts_pocket`, e.g. `standard:DF1:slight_over`. Used as the cell identity across the SPA and inspector.

---

## V3.1 Active Cells (20)

Source: `app/engine/static_policy.py::V3_ACTIVE`. Locked from 28,425-fixture analysis + 2026-05-27 DF separation evidence.

| Cell | Markets | Historical hit |
|------|---------|----------------|
| strong:DF0:slight_over | goals_nl | 70.9% (n=704) |
| strong:DF0:slight_under | goals_nl | 65.2% (n=851) |
| strong:DF1:slight_over | goals_nl | 72.6% (n=3712) |
| strong:DF1:slight_under | goals_nl | 66.7% (n=2525) |
| strong:DF2:slight_over | goals_nl | 71.4% (n=581) |
| strong:DF2:slight_under | goals_nl | 67.1% (n=2549) |
| standard:DF0:slight_over | goals_nl + corners_nl | 80.1 / 61.9 |
| standard:DF0:strong_over | goals_nl + corners_nl | 81.1 / 61.3 |
| standard:DF1:slight_over | goals_nl + corners_nl | 79.7 / 65.4 |
| standard:DF1:strong_over | goals_nl + corners_nl | 83.5 / 69.7 |
| standard:DF2:slight_over | goals_nl + corners_nl | 76.9 / 63.9 |
| standard:DF2:slight_under | goals_nl + corners_nl | 71.6 / 57.9 |
| standard:DF2:strong_over | goals_nl + corners_nl | 86.2 / 74.6 |
| low:DF2:slight_over | dnb | 84.9% |
| low:DF2:slight_under | dnb | 91.6% |
| low:DF2:strong_over | dnb | 82.8% |
| one_sided:DF2:slight_over | alpha_win | 76.6% |
| one_sided:DF2:slight_under | alpha_win | 81.0% |
| one_sided:DF2:strong_over | alpha_win | 66.7% (FLAG) |
| one_sided:DF2:strong_under | alpha_win | 80.9% (n=47, `min_n` lowered 50→45) |

---

## Markets

| Market | Full name | When fired | Pick label | Pick odd source |
|--------|-----------|------------|-----------|-----------------|
| `goals_nl` | Over 1.5 Goals | strong + standard | `"Over 1.5 Goals"` | `fixtures.goals_over_15_odd` (often NULL) |
| `corners_nl` | Over 8.5 Corners | standard | `"Over 8.5 Corners"` | `fixtures.corners_over_85_odd` (almost always NULL) |
| `dnb` | Draw No Bet | low (V3.1 activated) | Alpha team name | Derived `(1 − p_draw) / p_alpha` |
| `alpha_win` | Alpha Win | one_sided | Alpha team name | `min(home_odd, away_odd)` |

### Why pick_odd is often NULL on goals_nl / corners_nl
Sportmonks rarely quotes Over 1.5 Goals or Over 8.5 Corners (trivial lines). V3.1 policy is **natural-line only** — no fallback to Over 2.5 / Over 9.5 prices. The SPA renders `—` via `fmt.odd` when NULL. EV will come from Project 3 (breakeven_odds + live bookmaker price), not from `pick_odd`.

### DNB Derived Odd

```
p_home = 1 / home_odd
p_draw = 1 / draw_odd
p_away = 1 / away_odd
p_alpha = max(p_home, p_away)
dnb_odd = (1 - p_draw) / p_alpha
```

Pick card shows a `derived` flag.

---

## Pick Settlement

| Outcome | `actual_value` | Markets it applies to |
|---------|---------------|----------------------|
| WIN | 1.0 | All markets |
| VOID | 0.5 | DNB only |
| LOSS | 0.0 | All markets |

**Hit rate convention:** V3 non-loss — `(wins + voids) / settled`. Voids count as wins because stake is returned.

`pick_results.outcome` is the **string** label. `pick_results.actual_value` is the **float**. Filter on `outcome='WIN'` or use `actual_value` for arithmetic; mixing storage classes in SQLite returns garbage.

---

## Drift

| Flag | Condition |
|------|-----------|
| `stable` | gap > −5pp |
| `watch` | −10pp < gap ≤ −5pp |
| `drifting` | gap ≤ −10pp |
| `no_data` | recent_n < 10 |

Drift is informational — engine never auto-suppresses a cell. Per (zone, df, bts, market) baseline used.

---

## SPA Tabs — What Each Shows

### Tab 1: Picks
`GET /picks?days={n}` (default 7d). Each pick card: fixture, kickoff, partition key, market row(s), pick label, pick_odd (or `—`), drift chip.
Summary bar: count, fixtures, by market, skip reasons. CSV export → `paper_trading.csv`.

### Tab 2: Upcoming
`GET /upcoming?days={n}&tier={t}` (default 7d). Every classified fixture with V3.1 cell chip.

### Tab 3: Analysis
`GET /api/foundation`. Foundation matrix — live `compute_foundation()` output. ALL / T1 / T2+T3 sub-tabs.

### Tab 4: Inspector
- `GET /inspector/partition_drift` — drift table per active cell
- `GET /inspector/recent_settled` — recent fixtures with settled picks
- `GET /inspector/similar?fixture_id=…` — cell history for pre-match lens
- `GET /inspector/daily_calendar` — WIN/VOID/LOSS calendar

### Tab 5: Reports
- `/reports/emit_performance` — multi-window hit rates (legs + events)
- `/reports/emit_recent` — per-fixture readback
- `/reports/emit_market_breakdown` — per (zone, df, bts, market, pick) hit rates
- `/reports/settle_activity` — daily settlement counts + last pipeline heartbeat

### Tab 6: Today
`GET /diagnostics/today_summary`. Cron chip uses **any pipeline metric** in `system_health` (V3.1 — `fetch_upcoming` / `fetch_results` / `settle` / `emit_picks` / `refresh_odds` / `refresh_stats` / legacy `cron_heartbeat`). Fresh < 26h, warning 26–48h, stale > 48h, never_fired if none seen.

### Tab 7: Stats
`/diagnostics/db_state` + `/odds_coverage` + `/cron/heartbeat` + `/drift_report` + `/activity_by_tier`.

### Tab 8: Results
`GET /api/results?days={n}` + `GET /api/livescores`. Recent settled fixture history + Sportmonks live-in-play overlay (server-side proxy, ACTIVE_LEAGUES filter, 60s polling when match window open).

---

## League Tiers

| Tier | Description | Leagues |
|------|-------------|---------|
| T1 | Top-flight | PL, Ligue 1, La Liga, Serie A, Allsvenskan, Eliteserien, Besta deild, Veikkausliiga, Ireland Premier Division, MLS, Brazil Serie A, J1, K League 1 |
| T2 | Second-tier / strong regional | La Liga 2, Superettan, Ettan N/S, Copa Colombia, Primera B, Liga Pro Ecuador, Canada PL, Ykköseliga, Meistriliiga, Esiliiga A, USL Championship, J2/J3, China Super League |
| T3 | Development / lower | USL League One, MLS Next Pro, Bolivia Liga |

30 subscribed leagues in DB; ~62 total including historical seeds.

---

## Abbreviations Reference

| Abbrev | Full form |
|--------|-----------|
| DNB | Draw No Bet |
| BTS / BTTS | Both Teams To Score |
| DF | Difference Factor — V3.1 partition axis (rounded `|home_odd − away_odd|`) |
| NL / SL | Natural line / System line |
| pp | Percentage points |
| SM | Sportmonks |
| T1 / T2 / T3 | League tier |
| FK | Foreign key |
| emit | Engine generating + logging a pick |
| leg | A single market pick within a fixture emission |
| event | A (fixture, market) pair — collapses multi-leg picks |
| 1X2 | Home Win / Draw / Away Win market |
| alpha team | Favoured side (lower odd) |
| PROMOTE | Cell in V3_ACTIVE that emits picks |
| MEASURING | Foundation matrix tag for low-zone cells (display only — picks still fire) |
| cron | Scheduler — 12 Task Scheduler jobs |
| emit_log | Pick emission table |
| pick_results | Settlement table |
| partition | A (zone, DF, bts) cell |
| paper trading | CSV export for manual bookmaker tracking |
| chain | Legacy V3 audit-trail concept — not used in V4 |
| PRX9 | Retired V3 ranking layer — removed in V3.1 |

---

## Current System State (2026-05-28)

| Metric | Value |
|--------|-------|
| Active policy | V3.1 (20 cells, DF-aware) |
| DB fixtures total | 51,057 |
| DB fixtures settled | 46,905 |
| DB fixtures upcoming | 4,152 |
| fixture_stats | 38,574 |
| emit_log total | 613 — 275 settled, 338 pending |
| pick_results | 275 — 156W / 76L / 43V (non-loss 73.5% 7d) |
| Leagues in DB | 62 (30 subscribed + historical) |
| h2h_meetings | 58,881 |
| ngrok URL | https://steadier-legwarmer-finlike.ngrok-free.dev |
| Port | 8083 |

---

## How to Operate

### Daily — run scheduler or chained script
The scheduler handles this automatically (12 jobs registered via `setup_scheduler.ps1`). Manual fallback:

```powershell
Set-Location C:\OddsFlowV4
.\run_daily.ps1   # chains fetch_upcoming → emit_picks → fetch_results → settle + heartbeat
```

Or each step individually:
```powershell
python fetch_upcoming.py
python emit_picks.py
python fetch_results.py
python settle.py
```

### Server
Runs from Task Scheduler (`OddsFlow_Server`, auto-restart). Manual start:
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8083
```

### Ngrok
Runs from Task Scheduler (`OddsFlow_Ngrok`). Manual:
```powershell
ngrok http 8083
```

### Access
- Local SPA: http://localhost:8083
- Public: https://steadier-legwarmer-finlike.ngrok-free.dev
- Health: /health and /healthz/deep
- API docs: /docs
