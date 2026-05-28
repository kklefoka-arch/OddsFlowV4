# OddsFlow V4 — Engine Knowledge (V3)

> Living document. Updated at the end of each session.
> Last updated: 2026-05-28 (Session 19 — V3 restoration + raw-notes zone overlay)

---

## Engine Architecture

V4 is a football betting analytics engine. It ingests pre-match fixtures and odds from Sportmonks, classifies each fixture into a `(draw_zone × bts_pocket)` cell, and emits picks for the 9 cells in V3 active policy. The structured edge is in the (draw_odd × bts_parent) combination. Hit rate is the only edge metric.

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
[zone_of(draw_odd)] + [bts_of(yes, no)]
      |
      v
[V3_ACTIVE lookup] (static_policy.py — 9 cells)
      |
      ├── cell not active → skip (partition_not_promoted)
      ├── draw_odd missing → skip (unclassifiable)
      └── cell active → one or more markets emit
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
| `fetch_upcoming.py` | Daily fetch — fixtures + 1X2/BTTS/goals_over_*/corners_over_* odds |
| `emit_picks.py` | Calls `/picks?days=3` + writes `emit_picks` heartbeat |
| `refresh_odds.py` | Intraday odds refresh for next-8h fixtures (M2) |
| `refresh_stats.py` | 14-day corner-stats backfill (M3) |
| `fetch_results.py` | Scores + `fixture_stats` after match windows |
| `settle.py` | Writes `pick_results` |
| `app/engine/classify.py` | `zone_of()` (raw-notes overlay) + `bts_of()` |
| `app/engine/static_policy.py` | `V3_ACTIVE` / `V3_MARKETS` / `PROMOTED_CELLS` — 9 cells |
| `app/engine/promotion.py` | `compute_foundation()` — display only |
| `app/api/routes_picks.py` | `/picks` — V3 lookup + emit_log + drift |
| `app/api/routes_diagnostics.py` | today_summary + multi-metric cron heartbeat |
| `data/oddsflow_v4.db` | Live SQLite DB (not in git) |

### Database Tables

| Table | Purpose |
|-------|---------|
| `fixtures` | Fixture + odds + scores + `draw_zone` (raw-notes overlay) + `bts_pocket`. `df_level` retained but unused. |
| `teams` | Team registry |
| `leagues` | League registry + tier |
| `emit_log` | Pick emission log. `df_level` retained from V3.1 schema; new rows NULL. |
| `pick_results` | Settled outcomes |
| `system_health` | Heartbeats: `fetch_upcoming`, `fetch_results`, `settle`, `emit_picks`, `refresh_odds`, `refresh_stats`, `zone_migration`, legacy `cron_heartbeat` |
| `fixture_stats` | Corners + stats |
| `h2h_meetings` | ~58k rows; reserved for H2H corner-count signal work |

---

## Classification (two axes — V3)

### Draw Zone (`zone_of(draw_odd)`) — raw-notes overlay (Session 19)

| Zone | Draw odd range | Market |
|------|----------------|--------|
| (excluded) | `< 2.90` | both_sided — not classified |
| `strong` | `2.90 ≤ x < 3.30` | goals_nl + DNB |
| `standard` | `3.30 ≤ x < 3.80` | goals_nl + corners_nl + DNB |
| `low` | `3.80 ≤ x < 4.30` | DNB |
| `one_sided` | `≥ 4.30` | alpha_win |

### BTS Pocket (`bts_of(yes, no)`)

| Pocket | Condition |
|--------|-----------|
| `strong_over` | Yes favoured AND `yes_odd < 1.50` |
| `slight_over` | Yes favoured AND `yes_odd ≥ 1.50` |
| `strong_under` | No favoured AND `no_odd < 1.50` |
| `slight_under` | No favoured AND `no_odd ≥ 1.50` |

### Partition Key
`zone:bts_pocket` — e.g. `standard:slight_over`.

---

## V3 Active Cells (9)

Source: `app/engine/static_policy.py::V3_ACTIVE`.

| Cell | Markets | Reference hit (pre-overlay baseline) | n |
|------|---------|-------------------------------------|---|
| strong:slight_over | goals_nl + DNB | gn 72.2%, threeway 70.5% | 4,997 |
| strong:slight_under | goals_nl + DNB | gn 66.6%, threeway 74.9% | 5,925 |
| standard:slight_over | goals_nl + corners_nl + DNB | gn 78.2%, cn 64.5%, threeway 74.8% | 9,449 |
| standard:strong_over | goals_nl + corners_nl + DNB | gn 83.7%, cn 69.9%, threeway 69.4% | 1,319 |
| standard:slight_under | goals_nl + corners_nl + DNB | gn 71.6%, cn 57.8%, threeway 82.8% (MARGINAL) | 1,940 |
| low:slight_over | DNB | threeway 84.9% | 1,733 |
| low:slight_under | DNB | threeway 91.6% | 675 |
| one_sided:slight_over | alpha_win | threeway 76.6% | 1,119 |
| one_sided:slight_under | alpha_win | threeway 81.0% | 814 |

**Baselines are pre-overlay.** They were computed against the prior 2.70/3.40/4.10/4.80 boundaries. Treat as reference. 6 weeks of live settlement under the new boundaries will produce the new baseline.

---

## Markets

| Market | When fired | Pick label | Pick odd source |
|--------|------------|-----------|-----------------|
| `goals_nl` | strong + standard | `"Over 1.5 Goals"` | `fixtures.goals_over_15_odd` (often NULL) |
| `corners_nl` | standard | `"Over 8.5 Corners"` | `fixtures.corners_over_85_odd` (almost always NULL) |
| `dnb` | low | Alpha team name | Derived `(1 − p_draw) / p_alpha` |
| `alpha_win` | one_sided | Alpha team name | `min(home_odd, away_odd)` |

### Why pick_odd is often NULL on goals_nl / corners_nl
Sportmonks rarely quotes Over 1.5 / Over 8.5. V3 policy is natural-line only — no fallback to Over 2.5 / Over 9.5 prices. SPA renders `—`. EV / breakeven layer is *not* in the live engine (Durable Rule).

### DNB Derived Odd

```
p_home = 1 / home_odd
p_draw = 1 / draw_odd
p_away = 1 / away_odd
p_alpha = max(p_home, p_away)
dnb_odd = (1 − p_draw) / p_alpha
```

Pick card shows a `derived` flag.

---

## Pick Settlement

| Outcome | `actual_value` | Markets |
|---------|---------------|---------|
| WIN | 1.0 | All |
| VOID | 0.5 | DNB only |
| LOSS | 0.0 | All |

**Hit rate convention:** V3 non-loss — `(wins + voids) / settled`.

`pick_results.outcome` is the **string** label; `actual_value` is the **float**. Filter on `outcome='WIN'` or use `actual_value`; never numeric compare against `outcome` in SQLite.

---

## Drift

| Flag | Condition |
|------|-----------|
| `stable` | gap > −5pp |
| `watch` | −10pp < gap ≤ −5pp |
| `drifting` | gap ≤ −10pp |
| `no_data` | recent_n < 10 |

Drift is informational. Engine never auto-suppresses — operator reviews.

---

## SPA Tabs — What Each Shows

### Tab 1: Picks
`GET /picks?days={n}` (default 7d). Per pick: fixture, kickoff, partition key (`zone:bts`), market row(s), pick label, pick_odd (or `—`), drift chip. Summary bar: count, fixtures, by market, skip reasons. CSV → `paper_trading.csv`.

### Tab 2: Upcoming
`GET /upcoming?days={n}&tier={t}` (default 7d). Every classified fixture with V3 cell chip.

### Tab 3: Analysis
`GET /api/foundation`. Foundation matrix — `compute_foundation()` output. ALL / T1 / T2+T3 sub-tabs.

### Tab 4: Inspector
- `GET /inspector/partition_drift` — drift table per active cell
- `GET /inspector/recent_settled` — recent settled picks
- `GET /inspector/similar?fixture_id=…` — cell history (pre-match lens)
- `GET /inspector/daily_calendar` — WIN/VOID/LOSS calendar

### Tab 5: Reports
- `/reports/emit_performance` — multi-window hit rates
- `/reports/emit_recent` — per-fixture readback
- `/reports/emit_market_breakdown` — per (zone, bts, market, pick) hit rates
- `/reports/settle_activity` — daily settlement + last pipeline heartbeat

### Tab 6: Today
`GET /diagnostics/today_summary`. Cron chip uses any of the 7 pipeline metrics (V3.1 multi-metric fix retained).

### Tab 7: Stats
`/diagnostics/db_state` + `/odds_coverage` + `/cron/heartbeat` + `/drift_report` + `/activity_by_tier`.

### Tab 8: Results
`GET /api/results?days={n}` + `GET /api/livescores` — DB history + Sportmonks live overlay (server-side proxy, ACTIVE_LEAGUES filter, 60s polling).

---

## League Tiers

| Tier | Description | Examples |
|------|-------------|----------|
| T1 | Top-flight | PL, Ligue 1, La Liga, Serie A, Allsvenskan, Eliteserien, Besta deild, Veikkausliiga, Ireland PD, MLS, Brazil A, J1, K League 1 |
| T2 | Second-tier / strong regional | La Liga 2, Superettan, Ettan N/S, Copa Colombia, Primera B, Liga Pro Ecuador, Canada PL, Ykköseliga, Meistriliiga, Esiliiga A, USL Championship, J2/J3, China Super |
| T3 | Development / lower | USL League One, MLS Next Pro, Bolivia Liga |

30 subscribed; 62 in DB (incl. historical).

---

## Abbreviations Reference

| Abbrev | Full form |
|--------|-----------|
| DNB | Draw No Bet |
| BTS / BTTS | Both Teams To Score |
| NL / SL | Natural line / System line |
| pp | Percentage points |
| SM | Sportmonks |
| T1 / T2 / T3 | League tier |
| FK | Foreign key |
| emit | Engine generating + logging a pick |
| leg | A single market pick within a fixture emission |
| event | A (fixture, market) pair — collapses multi-leg picks |
| 1X2 | Home Win / Draw / Away Win |
| alpha team | Favoured side (lower odd) |
| PROMOTE | Cell in V3_ACTIVE that emits picks |
| MEASURING | Foundation matrix tag for low-zone cells (display only) |
| cron | Scheduler — 12 Task Scheduler jobs |
| partition | A (zone, bts) cell |
| paper trading | CSV export for manual bookmaker tracking |
| DF | Difference Factor — analysis-only signal, NOT a partition key in V4 |
| both_sided | draw_odd < 2.90 — excluded from V3 policy |
| PRX9 | Retired V3 ranking layer |

---

## Current System State (2026-05-28)

| Metric | Value |
|--------|-------|
| Active policy | **V3** (Session 11 baseline) — 9 cells, 2-key (zone, bts), raw-notes boundaries |
| DB fixtures total | 51,057 |
| DB fixtures settled | 46,905 |
| DB fixtures upcoming | 4,152 |
| draw_zone distribution (post-overlay) | strong 7,789 / standard 13,140 / low 3,982 / one_sided 3,840 / excluded 22,306 |
| fixture_stats | 38,574 |
| emit_log | 613 |
| pick_results | 275 — 156W / 76L / 43V (non-loss 73.5% 7d window, pre-restore) |
| Leagues in DB | 62 (30 subscribed) |
| h2h_meetings | 58,881 |
| ngrok URL | https://steadier-legwarmer-finlike.ngrok-free.dev |
| Port | 8083 |
| DB backup before restore | `data/oddsflow_v4.db.bak.2026-05-28-session19` |

---

## How to Operate

### Daily — run scheduler or chained script

```powershell
Set-Location C:\OddsFlowV4
.\run_daily.ps1
```

Or each step individually:
```powershell
python fetch_upcoming.py
python emit_picks.py
python fetch_results.py
python settle.py
```

### Server
Task Scheduler (`OddsFlow_Server`). Manual:
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8083
```

### Ngrok
Task Scheduler (`OddsFlow_Ngrok`). Manual:
```powershell
ngrok http 8083
```

### Access
- Local SPA: http://localhost:8083
- Public: https://steadier-legwarmer-finlike.ngrok-free.dev
- Health: /health and /healthz/deep
- API docs: /docs
