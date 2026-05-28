# OddsFlow V4

**This is the only OddsFlow project.** One folder, one repo, one DB.
Read this file at the start of every session. Update it at the end. Commit it.

Operator: Katlego (KK) | Port: 8083 | Repo: `github.com/kklefoka-arch/OddsFlowV4`
Host (local): `http://localhost:8083` | Host (ngrok): `https://steadier-legwarmer-finlike.ngrok-free.dev`

---

## Project overview

Football betting analytics engine. Ingests fixtures + odds from Sportmonks, classifies
each fixture into a (draw_zone × DF × bts_pocket) cell, and emits picks for the cells
in the active V3.1 policy.

**V3.1 policy (DF-aware partition — deployed 2026-05-27):**
20 active cells from 28,425-fixture analysis, partitioned across 4 zones × DF tier × BTS pocket.
DF (Difference Factor) is the rounded `|home_odd − away_odd|` and discriminates strongly within
zones (alpha_win DF separates 22–26pp Tier A/B; threeway lifts up to 12.6pp DF0→DF2).

Markets fired: goals_nl Over 1.5 (strong, standard), corners_nl Over 8.5 (standard only),
dnb (low), alpha_win (one_sided). Low zone is **active** (LOW_ZONE_SUPPRESS = False).
The previous V3 9-cell snapshot is superseded; live picks fire from `static_policy.V3_ACTIVE`.

## Current phase

**V3.1 policy live.** Picks fire from `static_policy.V3_ACTIVE` (NOT `compute_foundation`).
`compute_foundation()` still runs for `/api/foundation` analysis display.
DB (as of audit 2026-05-28): 51,057 fixtures (46,905 settled, 4,152 upcoming).
emit_log: 613 rows — 275 settled (156W / 76L / 43V, 73.5% non-loss hit), 338 pending.
fixture_stats: 38,574. Pipeline live; latest emit + settle within the past hour.

## Key files

| File | Purpose |
|------|---------|
| `fetch_upcoming.py` | Daily — refresh pre-match odds (1X2, BTTS, goals_over_15/25/35, corners_over_75/85/95) and full kickoff datetimes from Sportmonks |
| `emit_picks.py` | Calls local `/picks?days=3` to materialise picks into emit_log; writes heartbeat |
| `refresh_odds.py` | Intraday odds refresh for fixtures kicking off within the next 8h (M2) |
| `refresh_stats.py` | Backfill corner stats for settled fixtures Sportmonks delivered late (14d lookback, M3) |
| `fetch_results.py` | After matches — write scores + fixture_stats (corners via type_id=34) |
| `settle.py` | After fetch_results — write WIN/LOSS/VOID into pick_results (goals_nl, corners_nl, dnb, alpha_win) |
| `app/engine/static_policy.py` | `V3_ACTIVE` / `V3_MARKETS` / `PROMOTED_CELLS` — authoritative live policy |
| `app/engine/classify.py` | `zone_of()` + `bts_of()` + `df_of()` — three-axis classification |
| `app/engine/promotion.py` | `compute_foundation()` + PROMOTE thresholds — display matrix only, not pick firing |
| `app/engine/foundation.py` | `load_foundation(conn)` — settled fixture loader for the matrix |
| `app/api/routes_picks.py` | `/picks` — reads `V3_ACTIVE`, derives DNB odd, writes emit_log with supersede logic |
| `app/api/routes_foundation.py` | `GET /api/foundation` — full matrix JSON for Analysis tab |
| `app/api/routes_diagnostics.py` | `/diagnostics/today_summary` + cron heartbeat (multi-metric, V3.1) |
| `data/oddsflow_v4.db` | Live SQLite DB (not in git) |

## Decisions made

- **V3.1 policy (2026-05-27):** Picks fire from `static_policy.V3_ACTIVE` — not `compute_foundation()`.
  `compute_foundation()` still runs for `/api/foundation` Analysis display.
- **20 active cells** (zone × DF × bts_pocket):
  - **strong (6 cells):** DF0/1/2 × {slight_over, slight_under} → goals_nl Over 1.5
  - **standard (7 cells):** DF0/1 × {slight_over, strong_over}, DF2 × {slight_over, slight_under, strong_over} → goals_nl Over 1.5 + corners_nl Over 8.5
  - **low (3 cells):** DF2 × {slight_over, slight_under, strong_over} → dnb (alpha-win-or-draw)
  - **one_sided (4 cells):** DF2 × {slight_over, slight_under, strong_over, strong_under} → alpha_win
- **DF (Difference Factor):** `round(|home_odd − away_odd|)` clipped to DF0/DF1/DF2. Source: `app/engine/classify.py:df_of()`.
- **Low zone ACTIVATED** — `LOW_ZONE_SUPPRESS = False` in `static_policy.py`. (Note: `promotion.py` still defaults to `True` because that module powers the `/api/foundation` *display* matrix where low cells are reported as `MEASURING`; pick firing is independent.)
- **Goals NL uses natural line only** ("Over 1.5 Goals") — no effective-line fallback. Consequence: `pick_odd` is NULL on ~95% of goals_nl rows and 100% of corners_nl rows because Sportmonks rarely quotes Over 1.5 / Over 8.5 (trivial lines). This is by design; SPA renders `—` for null odds via `fmt.odd`. EV layer (Project 3) will use breakeven_odds + bookmaker price comparison, not the stored `pick_odd`.
- **Goals NL pick label:** "Over 1.5 Goals" — `settle.py` parses via regex `r"Over (\d+\.5) Goals"`.
- **Corners NL pick label:** "Over 8.5 Corners" — `settle.py` parses via regex `r"Over (\d+\.5) Corners"`.
- **settle.py** LEFT JOINs `fixture_stats` for corners_nl settlement.
- **PROMOTED_CELLS fallback** in inspector/reports updated to V3.1 (20 cells).
- **Drift tracking** is per (zone, df, bts_pocket, market) — corners_nl starts at `no_data` until enough recent settled rows exist.
- **Analysis tab** calls `/api/foundation` with ALL/T1/T2+T3 sub-tabs (compute_foundation for display).
- **`write_emit_log()`** supersedes stale unsettled picks when alpha team label changes.
- **fetch_upcoming.py** stores full kickoff datetimes; monthly windows July–Oct at `max_pages=30`, other months at `max_pages=20`.
- **Single SQLite DB** — no external DB services.
- **`fixtures.league_id`** stores internal DB `leagues.id` (resolved via `_league_id_map`).

## Daily flow

Order (run in sequence — `.\run_daily.ps1` chains them, otherwise each command runs once):

1. `python fetch_upcoming.py` — refresh pre-match odds + kickoff datetimes
2. `python emit_picks.py` — call `/picks?days=3` and record heartbeat (the API write is what populates emit_log)
3. `python fetch_results.py` — write scores + fixture_stats for completed fixtures
4. `python settle.py` — settle pending picks from emit_log into pick_results

Optional / supporting scripts driven by the scheduler:

- `python refresh_odds.py` — intraday odds refresh for fixtures kicking off within 8h
- `python refresh_stats.py` — corner-stats backfill (14d lookback) for fixtures Sportmonks delivered late

## Scheduler

12 Windows Task Scheduler jobs registered via `setup_scheduler.ps1` (run once as Admin).
Times below are SAST (UTC+2).

| Time | Task | Script |
|------|------|--------|
| **At system start** | OddsFlow_Server | uvicorn on :8083 (auto-restart) |
| **At system start** | OddsFlow_Ngrok | ngrok tunnel to :8083 (auto-restart) |
| 00:00 | OddsFlow_RefreshStats | refresh_stats.py — backfill late corners |
| 03:00 | OddsFlow_FetchResults_SA | fetch_results.py — South American window |
| 03:15 | OddsFlow_Settle_SA | settle.py |
| 06:00 | OddsFlow_FetchResults_DawnSA | fetch_results.py — late SA catch-up (M3) |
| 06:15 | OddsFlow_Settle_DawnSA | settle.py |
| 08:00 | OddsFlow_FetchUpcoming | fetch_upcoming.py |
| 08:05 | OddsFlow_EmitPicks | emit_picks.py — call /picks?days=3 |
| 14:30 | OddsFlow_RefreshOdds | refresh_odds.py — intraday refresh (M2) |
| 23:30 | OddsFlow_FetchResults | fetch_results.py — European window close |
| 23:45 | OddsFlow_Settle | settle.py |

Each task writes its own `system_health` heartbeat keyed by the metric name (e.g. `fetch_upcoming`, `settle`, `emit_picks`). The Today-tab cron card looks at the most recent timestamp across *any* pipeline metric (not just `cron_heartbeat`).

## Pending / next

- Project 2 calibration complete (2026-05-26):
  - Output at `C:\OddsFlow AI Website\Output\PROJECT2_CALIBRATION_2026-05-26.xlsx`
  - All V3.1 goals_nl/corners_nl cells NON_PROMOTE at avg market odds
  - alpha_win T1 = HOLD (+0.007 to +0.010 EV) — only EV-positive cells
  - Key metric: `breakeven_odds` per cell — any live price above this = EV+ bet
  - Edge source: price comparison across bookmakers, not avg-odds betting
- Project 3 (in design at `C:\OddsFlow AI Website`): live odds comparison layer — bookmaker price vs `breakeven_odds` per cell
- Monitor V3.1 corners_nl drift over next 2 weeks (recent_n still low for several cells)

## Reference documents

| Doc | Contents |
|-----|----------|
| `context/01_project_overview.md` | What, who, why (V3.1) |
| `context/02_league_config.md` | 30 leagues, tier assignments |
| `context/03_engine_rules.md` | Classification (zone × DF × bts) + V3.1 policy + market rules |
| `context/04_current_status.md` | Current state, known issues, session log |
| `context/05_architecture.md` | File map, process flow, API routes, DB tables |
| `context/06_process_flow.md` | Full fixture lifecycle — every phase, function, table, feedback loop |
| `context/07_system_language.md` | Every term defined; what exists vs what does not |
| `context/engine_knowledge.md` | Engine knowledge — tabs, abbreviations, architecture |
| `context/plan_group1_display.md` | Group 1 (G4/G7) — IMPLEMENTED, retained for audit trail |
| `context/plan_group2_data_quality.md` | Group 2 (G2/G3) — IMPLEMENTED, retained for audit trail |
| `context/plan_group3_automation.md` | Group 3 (G5/G6) — IMPLEMENTED, retained for audit trail |

## Session checklist

On start: scan directory → read CLAUDE.md → read `context/04_current_status.md`
On end: update `context/04_current_status.md` → update this file → commit → push
