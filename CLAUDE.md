# OddsFlow V4

**This is the only OddsFlow project.** One folder, one repo, one DB.
Read this file at the start of every session. Update it at the end. Commit it.

Operator: Katlego (KK) | Port: 8083 | Repo: `github.com/kklefoka-arch/OddsFlowV4`
Host (local): `http://localhost:8083` | Host (ngrok): `https://steadier-legwarmer-finlike.ngrok-free.dev`

---

## Project overview

Football betting analytics engine. Ingests fixtures + odds from Sportmonks, classifies
each fixture into a (draw_zone × bts_pocket) cell, and emits picks for promoted cells.

**V3 policy (ground zero — deployed 2026-05-25):**
9 active cells from 28,473-fixture analysis. 10 PASS / 1 MARGINAL / 1 FLAG.
Markets: goals_nl Over 1.5 (strong + standard), corners_nl Over 8.5 (standard only),
dnb (low zone), alpha_win (one_sided).

## Current phase

**V3 policy live.** Picks from static_policy.V3_ACTIVE (not compute_foundation).
Prior state: 392 emit_log rows — 192 settled (101W 35V 56L = 61.7%), 200 pending (old DNB policy).
Old pending picks (DNB for strong/standard) will continue to settle correctly.
New picks fire V3 markets from this session forward.
DB: 31,990 fixtures (28,801 settled, 3,189 upcoming).
Session 10: V3 policy deployed. static_policy.py → V3_ACTIVE. routes_picks.py → V3 markets.
settle.py → handles goals_nl, corners_nl, dnb, alpha_win.
Session 11: Server restart fixed (Windows --reload not working; killed + restarted process).
Low zone DNB picks confirmed firing. First V3 settlement: 36 picks — 22W 8L 6V.
goals_nl 85.7% (12/14), corners_nl 87.5% (7/8), DNB 6 voids (draws, stakes returned).
177 picks across 120 fixtures live. 3,174 upcoming fixtures refreshed.
Session 12: Daily pipeline run (no new results — non-match day). 253 pending picks.
Project 2 calibration complete. Breakeven odds documented per cell. alpha_win T1 = HOLD (EV+).
Total settled all-time: 228 (123W/64L/41V). Live picks via API: 39.

## Key files

| File | Purpose |
|------|---------|
| `fetch_upcoming.py` | Run daily — refresh pre-match odds + full kickoff datetimes from Sportmonks |
| `fetch_results.py` | Run after match days — writes scores + corners for completed fixtures |
| `settle.py` | Run after fetch_results.py — writes settled pick outcomes to pick_results |
| `app/engine/promotion.py` | `compute_foundation()` + PROMOTE/PROMOTE_TOLERANCE constants — live engine |
| `app/engine/foundation.py` | `load_foundation(conn)` — settled fixture loader |
| `app/engine/classify.py` | `zone_of()` + `bts_of()` — fixture classification |
| `app/api/routes_picks.py` | Pick generation — live foundation, emit_log write |
| `app/api/routes_foundation.py` | `GET /api/foundation` — full matrix JSON for Analysis tab |
| `data/oddsflow_v4.db` | Live SQLite DB (not in git) |

## Decisions made

- **V3 policy (2026-05-25):** Picks fire from static_policy.V3_ACTIVE — not compute_foundation().
  compute_foundation() still runs for /foundation analysis view only.
- 9 active cells: strong×{slight_over,slight_under}→goals_nl Over 1.5;
  standard×{slight_over,strong_over,slight_under}→goals_nl Over 1.5 + corners_nl Over 8.5;
  low×{slight_over,slight_under}→dnb; one_sided×{slight_over,slight_under}→alpha_win.
- Low zone ACTIVATED — LOW_ZONE_SUPPRESS=False. Validated: 84.9%/91.6% hit rates.
- Goals NL uses natural line only (Over 1.5 for strong/standard) — no effective-line fallback.
- Goals NL pick label: "Over 1.5 Goals" — settle.py parses via regex.
- Corners NL pick label: "Over 8.5 Corners" — settle.py parses via regex.
- settle.py LEFT JOINs fixture_stats for corners_nl settlement.
- Inspector/reports PROMOTED_CELLS fallback updated to V3 values (9 cells).
- Drift tracking is per (zone, bts, market) — corners_nl starts at no_data.
- Analysis tab calls /api/foundation with ALL/T1/T2+T3 sub-tabs (compute_foundation for display).
- write_emit_log() supersedes stale unsettled picks when alpha team label changes.
- fetch_upcoming.py stores full kickoff datetimes; monthly windows July–Oct (max_pages=30).
- Single SQLite DB — no external DB services.
- fixtures.league_id stores internal DB leagues.id (resolved via _league_id_map).

## Next steps

**Daily flow (in order):**
1. `python fetch_upcoming.py` — refresh pre-match odds + kickoff datetimes
2. `python fetch_results.py` — write scores + corners for completed fixtures
3. `python settle.py` — settle picks from emit_log into pick_results

Or run `.\run_daily.ps1` for all three steps + heartbeat in sequence.

**Pending:**
- Register cron: run `setup_scheduler.ps1` as Admin (one-time)
- Monitor V3 corners_nl picks settling over first 2 weeks (drift starts at no_data)
- Project 2 calibration COMPLETE (2026-05-26):
  - parameter_set.json at `C:\OddsFlow AI Website\Output\CALIBRATION_PARAMETER_SET_2026-05-26.json`
  - All V3 goals_nl/corners_nl cells NON_PROMOTE at avg market odds
  - alpha_win T1 = HOLD (+0.007 to +0.010 EV) — only EV-positive cells
  - KEY METRIC: breakeven_odds per cell — any live price above this = EV+ bet
  - Edge source confirmed: price comparison across bookmakers, not avg-odds betting
- Project 3: live odds comparison layer (bookmaker price vs breakeven_odds per cell)

## Reference documents

| Doc | Contents |
|-----|----------|
| `context/01_project_overview.md` | What, who, why |
| `context/02_league_config.md` | 30 leagues, tier assignments |
| `context/03_engine_rules.md` | Classification + promotion logic |
| `context/04_current_status.md` | Current state, known issues, session log |
| `context/05_architecture.md` | File map, process flow, API routes, DB tables |
| `context/06_process_flow.md` | **Full fixture lifecycle** — every phase, function, table, feedback loop, and gap |
| `context/07_system_language.md` | **System language** — every term defined; what exists vs what does not |
| `context/engine_knowledge.md` | Full engine knowledge — tabs, abbreviations, architecture |

## Session checklist

On start: scan directory → read CLAUDE.md → read `context/04_current_status.md`
On end: update `context/04_current_status.md` → update this file → commit → push
