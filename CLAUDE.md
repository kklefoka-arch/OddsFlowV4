# OddsFlow V4

**This is the only OddsFlow project.** One folder, one repo, one DB.
Read this file at the start of every session. Update it at the end. Commit it.

Operator: Katlego (KK) | Port: 8083 | Repo: `github.com/kklefoka-arch/OddsFlowV4`
Host (local): `http://localhost:8083` | Host (ngrok): `https://steadier-legwarmer-finlike.ngrok-free.dev`

---

## Project overview

Football betting analytics engine. Ingests fixtures + odds from Sportmonks, classifies
each fixture into a (draw_zone × bts_pocket) cell, and emits picks for promoted cells.
Markets: DNB (strong/standard zones), Alpha Win (one_sided zone), Goals NL (6 cells, Over 2.5 line).

## Current phase

**Production — 3 markets live: DNB, Alpha Win, Goals NL.** Picks from live `compute_foundation()`.
392 emit_log rows — 192 settled (101W 35V 56L = 61.7% hit rate), 200 pending.
By market 7d: dnb=267, goals_nl=112 (88% with odd), alpha_win=23. 11 cells promoted (incl. 1 tolerance).
DB: 31,990 fixtures (28,801 settled, 3,189 upcoming). All 8 SPA tabs + endpoints return 200.
Session 9: Full pipeline live. settlement working. Goals NL effective-line fallback active.

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

- Picks fire from live `compute_foundation()` — not hardcoded stone policy
- Analysis tab calls `/api/foundation` with ALL/T1/T2+T3 sub-tabs
- Goals NL uses effective-line fallback: natural line → over 2.5 → over 3.5 → over 1.5 (first quoted odd wins)
- Goals NL pick label matches quoted line (e.g. "Over 2.5 Goals") — settle.py parses label via regex
- write_emit_log() supersedes stale unsettled picks when alpha team label changes (prevents duplicate pairs)
- Inspector/reports use live `compute_foundation()` — not static `PROMOTED_CELLS`
- Low zone suppressed (MEASURING) — accumulating data
- `fetch_upcoming.py` stores full kickoff datetimes ("2026-05-23 21:00:00"), not date-only; start window = TODAY
- fetch_upcoming.py uses monthly windows for July–Oct (max_pages=30) to avoid 1,000-fixture page cap
- Single SQLite DB — no external DB services
- `fixtures.league_id` stores internal DB leagues.id (resolved via `_league_id_map`)

## Next steps

**Daily flow (in order):**
1. `python fetch_upcoming.py` — refresh pre-match odds + kickoff datetimes
2. `python fetch_results.py` — write scores + corners for completed fixtures
3. `python settle.py` — settle picks from emit_log into pick_results

Or run `.\run_daily.ps1` for all three steps + heartbeat in sequence.

**Pending:**
- Register cron: run `setup_scheduler.ps1` as Admin (one-time)
- EV analysis for goals_nl markets: compare gs_hit (54–65%) vs Over 2.5 market price
- 3 drifting cells to monitor: one_sided:slight_over, standard:strong_over, strong:slight_over

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
