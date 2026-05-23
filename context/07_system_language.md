# OddsFlow V4 — System Language

Every term this system uses, defined exactly. When something is requested, reported, or questioned — this is the reference for what it means, where it lives, and what it connects to.

---

## Core Concepts

### Fixture
A single football match. Lives in the `fixtures` table.
- **Upcoming fixture**: `home_score IS NULL` — match has not been settled yet
- **Settled fixture**: `home_score IS NOT NULL` — match result is in the DB
- **Classifiable fixture**: has `draw_odd`, `btts_yes_odd`, `btts_no_odd` (all not NULL)

### Odds
The bookmaker prices attached to a fixture. Five are used by this system:
| Field | What it is |
|-------|-----------|
| `home_odd` | 1X2 price for home win |
| `draw_odd` | 1X2 price for draw |
| `away_odd` | 1X2 price for away win |
| `btts_yes_odd` | Both Teams To Score — Yes price |
| `btts_no_odd` | Both Teams To Score — No price |

Other odds exist in the schema (`goals_over_*`, `corners_over_*`) but are not currently extracted or used.

### Alpha Team
The team with the lower (more favoured) 1X2 odd. `home_odd ≤ away_odd` → home is alpha. Used to determine which team the pick is on and to compute the DNB odd.

### Draw Zone
Classification of a fixture based on its `draw_odd`. Represents how likely a draw is.
See: `zone_of()` in `app/engine/classify.py`. See Phase 3 in `06_process_flow.md`.

### BTS Pocket
Classification of a fixture based on its `btts_yes_odd` and `btts_no_odd`. Represents market expectation of whether both teams score.
See: `bts_of()` in `app/engine/classify.py`. See Phase 3 in `06_process_flow.md`.

### Cell
A (draw_zone × bts_pocket) combination. There are up to 16 cells (4 zones × 4 pockets). Each cell accumulates historical hit rates and receives a promotion decision. The foundation matrix is a table of cells.

### Tier
League quality tier. Assigned in `ACTIVE_LEAGUES` in `fetch_upcoming.py`.
- Tier 1: Top leagues (Premier League, La Liga, Serie A, etc.)
- Tier 2: Second-tier leagues
- Tier 3: Third-tier leagues
Stored in `fixtures.tier` and `leagues.tier`.

---

## Classification Terms

### Classify
To assign a fixture to a (draw_zone, bts_pocket) cell from its odds. Done by `classify_fixture()`. Stateless — computed on-the-fly, not stored. A fixture is classifiable only if it has `draw_odd`, `btts_yes_odd`, and `btts_no_odd`.

### Natural Line
The expected total (goals or corners) for fixtures in a given draw zone. `natural_line(zone, market)`. Used as the lower threshold in foundation matrix computation (gn_hit, cn_hit). See `app/engine/natural_lines.py`.

### System Line
One step above the natural line. `system_line(zone, market)`. Used as the upper threshold (gs_hit, cs_hit). The gap between natural hit and system hit is called the **drop**.

### Drop
`natural_hit - system_hit` (percentage points). Measures fragility: a high drop means performance is barely clearing the natural line and collapses at the system line. Lower drop = more robust.

### Drop Rank
Within a zone, cells are ranked by drop (ascending). Rank 1 = lowest drop = best performance structure. Used in PROMOTE_TOLERANCE qualification.

---

## Promotion Terms

### Calibration
The process of computing hit rates and promotion status for each cell across all settled fixtures. Done by `compute_foundation()`. Not a one-time setup — recalculated on every `/api/foundation` or `/picks` call.

### Baseline
The historical threeway hit rate for a cell, as computed by the foundation matrix across all 28,477+ settled fixtures. This is the reference number. Drift is measured against the baseline.

### Foundation Matrix
The full table of cells with their hit rates and promotion statuses. Produced by `load_foundation()` + `compute_foundation()`. Served at `GET /api/foundation`.

### Promoted Cell
A cell where `threeway_promote` is `PROMOTE` or `PROMOTE_TOLERANCE` and `zone != "low"`. This is what determines whether a fixture generates a pick. **V4 uses threeway promotion only.** Goals and corners promotion exist in the matrix but do not drive picks.

### PROMOTE
`threeway_hit ≥ 72.0%`. Hard promotion — cell consistently supports alpha win or draw.

### PROMOTE_TOLERANCE
`67.5% ≤ threeway_hit < 72.0%` AND drop rank qualifies (rank 1, or drop ≤ rank-1 drop + 4.5pp). Softer promotion with structural qualification.

### HOLD
`67.5% ≤ threeway_hit < 72.0%` but drop rank fails. Not promoted — performance is in range but structurally fragile.

### NO
`threeway_hit < 67.5%`. Not promoted.

### MEASURING
Cell would be PROMOTE or PROMOTE_TOLERANCE but `zone = "low"`. Suppressed — not enough data, accumulating. Low zone is excluded from pick generation.

### `cell_promoted`
True if ANY of goals_promote, corners_promote, threeway_promote is PROMOTE or PROMOTE_TOLERANCE. Used for display in the Analysis tab. NOT what drives picks — picks use `threeway_promote` only. The `summary.promoted_cells` count reflects threeway-promoted cells only.

---

## Pick Terms

### Pick
A recommendation generated for a specific upcoming fixture in a promoted cell.
- **Market**: DNB or Alpha Win
- **Pick label**: the alpha team's name
- **Pick odd**: the derived price

### DNB (Draw No Bet)
Market for strong and standard draw zones. Bet on the alpha team:
- Alpha wins → WIN (1.0)
- Draw → VOID (0.5, stake returned)
- Alpha loses → LOSS (0.0)

DNB odd is derived: `(1 - p_draw) / p_alpha` where `p = 1/odd`.

### Alpha Win
Market for one_sided draw zone. Bet on the alpha team to win outright:
- Alpha wins → WIN (1.0)
- Draw → LOSS (0.0)
- Alpha loses → LOSS (0.0)

Alpha Win odd = `min(home_odd, away_odd)`.

### Emit
The act of writing a pick to `emit_log`. Idempotent — same fixture + market + pick always produces the same `pick_uuid`. Running `/picks` multiple times is safe.

### `pick_uuid`
`SHA256("{fixture_id}:{market}:{pick_label}")[:36]`. Unique identifier for a pick. Primary key of `emit_log`. Also references `pick_results`.

### `emit_log`
The record of every pick that has been emitted. Each row: which fixture, which cell, which market, which pick, what odd, when emitted. This is the system's record of what it recommended and when.

### `confidence`
`threeway_hit / 100` — stored in `emit_log`. The cell's historical hit rate expressed as a decimal (e.g., 0.749 for 74.9%).

---

## Settlement Terms

### Settle
To resolve a pick's outcome against the final match result. Produces WIN / VOID / LOSS.
Done by `settle_pick()` (in `routes_picks.py`) and `settle.py`.

**Not the same as "emit"**. Emitting happens before the match. Settling happens after.

### `pick_results`
The table of settled outcomes. Written by `settle.py`. One row per `pick_uuid`. Fields: settled_at, outcome (WIN/VOID/LOSS), actual_value (1.0/0.5/0.0).

### On-the-fly settlement
Computing outcomes in memory from `emit_log` + fixture scores, without reading `pick_results`. Done by `routes_reports.py` (`emit_performance`, `emit_recent`). Works as long as fixture scores are in the DB. Does NOT require `settle.py` to have run.

### Persistent settlement
Outcomes written to `pick_results` by `settle.py`. Required for Inspector calendar (`daily_calendar`) and Inspector settled view (`recent_settled`).

### Outcome values
| Label | `actual_value` | Meaning |
|-------|---------------|---------|
| WIN | 1.0 | Pick hit |
| VOID | 0.5 | Draw, stake returned (DNB only) |
| LOSS | 0.0 | Pick failed |

---

## Drift Terms

### Drift
The difference between a cell's recent hit rate and its historical baseline.
`gap_pp = recent_hit - baseline_hit` (in percentage points).

### Drift Flag
| Flag | Condition | Meaning |
|------|-----------|---------|
| `stable` | gap > -5pp | Recent performance matches baseline |
| `watch` | -10pp < gap ≤ -5pp | Underperforming — monitor |
| `drifting` | gap ≤ -10pp | Significantly underperforming — review promotion |
| `no_data` | < 10 settled emits | Too few settled picks to evaluate |

---

## Reporting Terms

### Emit Performance
Multi-window summary (1d/3d/7d/30d/90d/180d) of pick outcomes. On-the-fly settlement from emit_log. Route: `GET /reports/emit_performance`.

### Emit Recent
Per-fixture readback of what was emitted and how it resolved. On-the-fly. Route: `GET /reports/emit_recent`.

### Settle Activity
Per-day settlement counts from `pick_results`. Requires settle.py to have run. Route: `GET /reports/settle_activity`.

### Market Breakdown
Per-(zone, bts, market, pick) hit rates. On-the-fly. Route: `GET /reports/emit_market_breakdown`.

### Inspector
The pre-match and post-match monitoring interface. Contains:
- **Partition Drift**: per-cell drift across all promoted cells
- **Recent Settled**: fixtures with settled picks (reads pick_results)
- **Daily Calendar**: per-day win/void/loss counts (reads pick_results)

---

## Process Terms

### Fetch
Pull upcoming fixtures and odds from Sportmonks. Script: `fetch_upcoming.py`. Frequency: daily, manual.

### Score Update
Write fixture results (home_score, away_score, total_goals, corner stats) to the DB after matches are played. **[GAP]** — not yet built. Script would be `fetch_results.py`.

### Settlement Run
Execute `settle.py` after matches complete. Frequency: after each match day, manual.

### Recalibrate
Re-run `compute_foundation()`. Happens automatically on every `/api/foundation` or `/picks` call — no explicit step needed.

---

## Tables

| Table | Purpose | Written by | Read by |
|-------|---------|-----------|---------|
| `leagues` | League reference | seed scripts | everywhere |
| `teams` | Team reference | fetch_upcoming.py | fixtures joins |
| `fixtures` | All fixture data (odds + results) | fetch_upcoming.py, [fetch_results.py GAP] | all routes |
| `fixture_stats` | Corners + match stats | [GAP] | load_foundation |
| `emit_log` | Pick emission record | routes_picks.py | reports, inspector, settle.py |
| `pick_results` | Settled pick outcomes | settle.py | inspector/recent_settled, inspector/daily_calendar, reports/settle_activity |
| `system_health` | Cron heartbeat | [automation GAP] | reports/settle_activity |
| `h2h_meetings` | Head-to-head history | [not currently populated] | not currently used |

---

## What Does Not Exist

These are things that sound like they might exist or that are often referenced but are NOT built:

| Missing | What it would do |
|---------|-----------------|
| `fetch_results.py` | Fetch match scores from Sportmonks and write to fixtures table |
| Automated score update | Any cron / scheduler writing scores after matches |
| Similar-odds history endpoint | Inspector pre-match lens showing historical fixtures with similar odds |
| Cron / scheduler | Automated daily fetch + settle |
| Goals/corners picks | Foundation matrix computes them; they are NOT used in V4 pick generation |
| PRX9 | Retired — `GET /picks/prx9` returns empty |
| Ingest pipeline for `draw_zone`/`bts_pocket` columns | Schema has them; nothing writes them |
