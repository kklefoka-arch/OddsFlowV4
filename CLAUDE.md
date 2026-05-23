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

**Production — picks live.** 170 picks in 3-day window (157 dnb, 13 alpha_win).
DB: 32,993 fixtures (28,602 settled, 4,391 upcoming). All 7 SPA tabs verified.
Session 2026-05-23 LATE: league_id bug fixed, fetch run, all tabs tested, engine_knowledge.md created.

## Key files

| File | Purpose |
|------|---------|
| `fetch_upcoming.py` | Run daily — refresh pre-match odds from Sportmonks |
| `app/engine/static_policy.py` | 10 promoted cells — stone policy, never changes |
| `app/engine/classify.py` | zone_of() + bts_of() — fixture classification |
| `app/api/routes_picks.py` | Pick generation + emit_log write |
| `data/oddsflow_v4.db` | Live SQLite DB (not in git) |

## Decisions made

- Stone policy locked from 28,425 settled fixtures — 10 cells, hit rates 69–88%
- No goals/corners markets — DNB and Alpha Win only
- Low zone suppressed (MEASURING) — accumulating data
- Single SQLite DB — no external DB services
- `fixtures.league_id` must store internal DB leagues.id — fetch_upcoming.py patched to resolve via `_league_id_map`

## Next steps

1. Run `python fetch_upcoming.py` daily for fresh odds
2. Monitor Reports tab — pick_results will populate as upcoming fixtures settle
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
