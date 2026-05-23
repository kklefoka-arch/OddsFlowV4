# OddsFlow V4

**This is the only OddsFlow project.** One folder, one repo, one DB.
Read this file at the start of every session. Update it at the end. Commit it.

Operator: Katlego (KK) | Port: 8083 | Repo: `github.com/kklefoka-arch/OddsFlowV4`

---

## Project overview

Football betting analytics engine. Ingests fixtures + odds from Sportmonks, classifies
each fixture into a (draw_zone × bts_pocket) cell, and emits picks for 10 promoted cells.
Markets: DNB (strong/standard zones) or Alpha Win (one_sided zone). No goals/corners in V4.

## Current phase

**Production — V3 engine live, zero-based test passed.** Picks from live `compute_foundation()`.
162 picks in 3-day window (151 dnb, 11 alpha_win). 10 cells promoted, hit rates 69–88%.
DB: 32,993 fixtures (28,477 settled, 4,391 upcoming). All 7 SPA tabs + 11 endpoints return 200.
Session 5: Zero-based 6-phase test, 4 bugs fixed (date filter, live foundation, promoted_cells count, settle.py).

## Key files

| File | Purpose |
|------|---------|
| `fetch_upcoming.py` | Run daily — refresh pre-match odds + full kickoff datetimes from Sportmonks |
| `settle.py` | Run after matches complete — writes settled picks to pick_results table |
| `app/engine/promotion.py` | `compute_foundation()` + PROMOTE/PROMOTE_TOLERANCE constants — live engine |
| `app/engine/foundation.py` | `load_foundation(conn)` — settled fixture loader |
| `app/engine/classify.py` | `zone_of()` + `bts_of()` — fixture classification |
| `app/api/routes_picks.py` | Pick generation — live foundation, emit_log write |
| `app/api/routes_foundation.py` | `GET /api/foundation` — full matrix JSON for Analysis tab |
| `data/oddsflow_v4.db` | Live SQLite DB (not in git) |

## Decisions made

- Picks fire from live `compute_foundation()` — not hardcoded stone policy
- Analysis tab calls `/api/foundation` with ALL/T1/T2+T3 sub-tabs
- No goals/corners markets — DNB (strong/standard) and Alpha Win (one_sided) only
- Low zone suppressed (MEASURING) — accumulating data
- `fetch_upcoming.py` stores full kickoff datetimes ("2026-05-23 21:00:00"), not date-only
- Single SQLite DB — no external DB services
- `fixtures.league_id` stores internal DB leagues.id (resolved via `_league_id_map`)

## Next steps

1. Run `python fetch_upcoming.py` daily — refreshes odds + kickoff datetimes
2. Run `python settle.py` after matches complete — writes pick_results (enables Inspector calendar)
3. Consider bumping fetch windows for July–Oct (hitting 1,000-fixture cap)

## Reference documents

| Doc | Contents |
|-----|----------|
| `context/01_project_overview.md` | What, who, why |
| `context/02_league_config.md` | 30 leagues, tier assignments |
| `context/03_engine_rules.md` | Classification + promotion logic |
| `context/04_current_status.md` | Current state, known issues, session log |
| `context/05_architecture.md` | File map, process flow, API routes, DB tables |
| `context/engine_knowledge.md` | Full engine knowledge — tabs, abbreviations, architecture |

## Session checklist

On start: scan directory → read CLAUDE.md → read `context/04_current_status.md`
On end: update `context/04_current_status.md` → update this file → commit → push
