# Group 1 Plan — Display Layer
## Gaps: G4 (Similar-Odds Inspector), G7 (Results Display)

**Phase connection:** Phase 8 (Score Update) → Phase 10 (Reports) → Phase 12 (Validate/Drift)
**Status:** PLANNED — not yet implemented

---

## G7 — Results Display

### What this closes
Fixture scores written by `fetch_results.py` are in the DB but have no frontend. Operator has no view of recent results without querying SQLite directly.

### Approach: Hybrid — DB history + Sportmonks livescores

#### Part A — Results History Tab (DB query)
**New SPA tab:** Results (8th tab)

**Backend route:** `GET /api/results`
- Query: `fixtures WHERE home_score IS NOT NULL AND substr(date,1,10) >= (today - N days)`
- Join: `fixture_stats` for corners (if available)
- Params: `days=7` (default), `league_id` (optional filter)
- Returns: fixture list with home_team, away_team, home_score, away_score, total_goals, home_corners, away_corners, date, league_id, tier

**Frontend display:**
- Date-grouped rows (today, yesterday, etc.)
- Score badge: home_score — away_score
- Corner line below score if available
- League filter dropdown (same pattern as Picks tab)
- Settled picks overlay: if a pick was emitted on this fixture, show outcome badge (WIN/VOID/LOSS) — source: emit_log JOIN pick_results

#### Part B — Livescores In-Play (Sportmonks)
**New backend route:** `GET /api/livescores`
- Proxies: `GET /v3/football/livescores/inplay?include=scores;participants`
- Filters: response filtered to `ACTIVE_LEAGUES` only (never exposes fixtures outside our scope)
- Returns: in-play fixtures with current score, minute, status
- **Token stays server-side** — frontend never calls Sportmonks directly

**Frontend behaviour:**
- Polling: every 60 seconds when the Results tab is active
- Match window detection: if any upcoming fixture has kickoff within the last 120 minutes → poll
- In-play badge on fixture row: score + minute (e.g. "2–1 · 67'")
- When status transitions to finished: row moves from in-play to settled view

**Auto-trigger hook (cross-cut to G5/G6):**
- When livescores returns a fixture with status=finished AND fixture is in our DB with home_score IS NULL:
  - Backend writes score + stats inline (same logic as fetch_results.py)
  - Backend runs settle logic for any emit_log entry on that fixture
  - This closes G5 (manual settle trigger) for match-day automation without a cron

### Files to create/modify
| File | Change |
|------|--------|
| `app/api/routes_results.py` | New — GET /api/results + GET /api/livescores |
| `app/frontend/templates/engine_view.html` | Add Results tab |
| `app/frontend/static/engine.js` | Results tab render + livescores polling |
| `app/main.py` | Register routes_results router |

### API endpoint reference
- In-play: `GET /v3/football/livescores/inplay?include=scores;participants&api_token=TOKEN`
- Filters applied server-side by league_id membership in ACTIVE_LEAGUES

---

## G4 — Similar-Odds Inspector (Pre-Match Lens)

### What this closes
Inspector pre-match view has no historical context. Operator cannot see "what happened last time this cell was promoted." No basis for pre-match confidence check.

### Approach: Inspector endpoint — cell history query

**New backend route:** `GET /inspector/similar`
- Params: `fixture_id=X` OR `zone=strong&bts=strong_over`
- If fixture_id: classify fixture on-the-fly → derive zone + bts_pocket
- Query: settled fixtures in same (zone, bts_pocket) cell, last N settled (default 50)
- Returns: list of recent fixtures in same cell with scores, pick outcomes (if emitted)

**Response shape:**
```json
{
  "zone": "strong",
  "bts_pocket": "strong_over",
  "cell_n": 3420,
  "threeway_hit": 74.2,
  "recent": [
    {
      "date": "2026-05-22",
      "home_team": "Shamrock Rovers",
      "away_team": "Sligo Rovers",
      "home_score": 1,
      "away_score": 2,
      "threeway_green": false,
      "emitted": true,
      "outcome": "LOSS"
    },
    ...
  ]
}
```

**Inspector tab integration:**
- Each promoted fixture card gets a "History" button → opens modal with similar-odds table
- Shows cell hit rate (from foundation) + recent fixture list
- Helps operator validate a pick before a match window

### Files to create/modify
| File | Change |
|------|--------|
| `app/api/routes_inspector.py` | Add GET /inspector/similar |
| `app/frontend/static/engine.js` | Inspector tab — history modal |
| `app/frontend/templates/engine_view.html` | History modal markup |

---

## Cross-cut summary

| G7 livescores path enables | Effect on other gaps |
|----------------------------|---------------------|
| Auto score write on match finish | G5 (manual settle) — closed for match-day fixtures |
| Backend-controlled polling | G6 (cron) — fetch_upcoming.py still needs scheduling; settle does not |
| Settled picks overlay in Results tab | G4 data is already computable — no separate query needed |

**Group 3 scope reduction if Group 1 livescores path is fully implemented:**
- G5 closed entirely (settle triggered by livescores finish event)
- G6 reduced to fetch_upcoming.py daily scheduling only

---

## Implementation order within group

1. `routes_results.py` — GET /api/results (DB query, no API dependency)
2. Results tab in SPA — history view from DB
3. `GET /api/livescores` — Sportmonks proxy, ACTIVE_LEAGUES filter
4. Livescores polling in frontend — in-play overlay
5. Auto-trigger hook — score write + settle on finish event
6. `GET /inspector/similar` — cell history endpoint
7. Inspector tab — history modal

Steps 1–2 can ship without Steps 3–5. Start with history, add live.
