# OddsFlow V4 — Engine Knowledge

> Living document. Updated at the end of each session.
> Last updated: 2026-05-23

---

## Engine Architecture

OddsFlow V4 is a football betting analytics engine. It ingests pre-match fixtures and odds from the Sportmonks API, classifies each fixture into a (draw_zone × bts_pocket) cell, and emits picks only for the 10 cells promoted by a stone policy locked from 28,425 settled fixtures.

### Process Flow

```
[Sportmonks API]
      |
      | fetch_upcoming.py (run daily)
      v
[fixtures table]  ←── teams, leagues tables
      |
      | classify_fixture()
      v
[zone_of(draw_odd)]  +  [bts_of(btts_yes_odd, btts_no_odd)]
      |
      v
[PROMOTED_CELLS lookup] (static_policy.py)
      |
      ├── cell not promoted → skip (partition_not_promoted)
      ├── draw_odd missing  → skip (unclassifiable)
      └── cell promoted     → emit pick
                                   |
                              [emit_log table]
                                   |
                    ┌──────────────┴──────────────┐
                 [dnb]                       [alpha_win]
              derive DNB odd               take min(home,away)
              from 1X2 prices              as pick_odd
```

### Key Files

| File | Role |
|------|------|
| `fetch_upcoming.py` | Daily fetch — Sportmonks API → fixtures + odds into DB |
| `app/engine/classify.py` | `zone_of()` + `bts_of()` — two-axis fixture classification |
| `app/engine/static_policy.py` | `PROMOTED_CELLS` — stone policy, 10 cells, never changes |
| `app/api/routes_picks.py` | Pick generation + emit_log write + drift annotation |
| `app/api/routes_upcoming.py` | All upcoming fixtures with classification labels |
| `app/api/routes_analysis.py` | Per-cell hit rates from settled fixtures |
| `app/api/routes_inspector.py` | Drift tracking per promoted cell |
| `app/api/routes_reports.py` | Post-match performance + CSV export |
| `app/api/routes_diagnostics.py` | Today summary + DB state + cron heartbeat |
| `app/db/database.py` | SQLite connection helper |
| `app/settings.py` | Config (DB path, log level, env) |
| `app/frontend/templates/engine_view.html` | SPA shell — 7 tabs |
| `app/frontend/static/engine.js` | All tab logic, fetch calls, rendering |
| `data/oddsflow_v4.db` | Live SQLite DB (not in git) |
| `scripts/update_leagues.py` | One-off: upsert 30 subscribed leagues |

### Database Tables

| Table | Purpose |
|-------|---------|
| `fixtures` | Pre-match + post-match fixture records with odds and scores |
| `teams` | Team registry (name + Sportmonks ID) |
| `leagues` | League registry (name, country, tier, Sportmonks ID) |
| `emit_log` | Every pick the engine emitted — idempotent via `pick_uuid` |
| `pick_results` | Post-match settlement of emitted picks (WIN/VOID/LOSS) |
| `system_health` | Cron heartbeat and error logs |
| `fixture_stats` | Extended match stats (goals, corners — from calibration DB) |
| `h2h_meetings` | Head-to-head historical meetings |

---

## Classification System

### Draw Zone (axis 1 — `zone_of`)

Derived from the bookmaker draw odd:

| Zone | Draw odd range | Market |
|------|---------------|--------|
| `strong` | 2.70 ≤ odd < 3.40 | DNB |
| `standard` | 3.40 ≤ odd < 4.10 | DNB |
| `low` | 4.10 ≤ odd < 4.80 | MEASURING (suppressed) |
| `one_sided` | odd ≥ 4.80 | Alpha Win |
| *(excluded)* | odd < 2.70 | Not classified |

### BTS Pocket (axis 2 — `bts_of`)

Derived from BTTS Yes and No odds:

| Pocket | Condition |
|--------|-----------|
| `strong_over` | Yes favoured AND yes_odd < 1.50 |
| `slight_over` | Yes favoured AND yes_odd ≥ 1.50 |
| `strong_under` | No favoured AND no_odd < 1.50 |
| `slight_under` | No favoured AND no_odd ≥ 1.50 |

"Yes favoured" = yes_odd ≤ no_odd.

### Partition Key

Written as `zone:bts_pocket` — e.g., `standard:slight_over`. This is the cell identity used throughout the SPA.

---

## Stone Policy — 10 Promoted Cells

Locked from 28,425 settled fixtures. Never changes with local DB state.

| Cell (zone:bts) | Market | Hist hit % | n fixtures | Promote status |
|----------------|--------|-----------|-----------|----------------|
| strong:slight_over | DNB | 70.5% | 4,997 | PROMOTE_TOLERANCE |
| strong:slight_under | DNB | 74.9% | 5,925 | PROMOTE |
| strong:strong_under | DNB | 87.9% | 33 | PROMOTE |
| standard:slight_over | DNB | 74.8% | 9,449 | PROMOTE |
| standard:strong_over | DNB | 69.4% | 1,319 | PROMOTE_TOLERANCE |
| standard:slight_under | DNB | 82.8% | 1,940 | PROMOTE |
| standard:strong_under | DNB | 84.6% | 26 | PROMOTE |
| one_sided:slight_over | Alpha Win | 76.6% | 1,119 | PROMOTE |
| one_sided:slight_under | Alpha Win | 81.0% | 814 | PROMOTE |
| one_sided:strong_under | Alpha Win | 80.9% | 47 | PROMOTE |

**PROMOTE_TOLERANCE** = cell promoted despite borderline statistical confidence.
3-Way baseline avg across all 10 promoted cells: 74.6%.

---

## Markets

| Market | Full name | When used | Pick = |
|--------|-----------|-----------|--------|
| `dnb` | Draw No Bet | strong and standard draw zones | Favourite (alpha team) — DNB returns stake if draw |
| `alpha_win` | Alpha Win | one_sided draw zone | Favourite must win outright — no draw protection |

### Alpha Team

The team with the lower (more favoured) 1X2 odd. If home_odd ≤ away_odd → alpha is home, else away.

### DNB Derived Odd

For DNB, bookmakers don't always quote a direct DNB price. The engine derives it from the 1X2 prices:

```
p_home = 1 / home_odd
p_draw = 1 / draw_odd
p_away = 1 / away_odd
p_alpha = max(p_home, p_away)
dnb_odd = (1 - p_draw) / p_alpha
```

When derived: the pick card shows a `derived` flag — this is not a quoted bookmaker price.

---

## Pick Settlement

| Outcome | Condition |
|---------|-----------|
| WIN (1.0) | Alpha team wins |
| VOID (0.5) | Draw (DNB only) — stake returned |
| LOSS (0.0) | Alpha team loses |

Alpha Win does not void on draw — a draw is a LOSS for Alpha Win.

---

## Drift

The engine tracks whether each promoted cell is performing recently vs its historical baseline.

| Flag | Condition |
|------|-----------|
| `stable` | Recent hit rate within 5pp of historical |
| `watch` | Recent hit rate 5–10pp below historical |
| `drifting` | Recent hit rate >10pp below historical |
| `no_data` | Fewer than 10 settled emits in the window |

**Display only** — drift flags are informational. The engine does NOT auto-suppress drifting cells.

---

## League Tiers

30 subscribed leagues in 3 tiers:

| Tier | Description | Leagues |
|------|-------------|---------|
| T1 | Top-flight | PL, Ligue 1, La Liga, Serie A, Allsvenskan, Eliteserien, Besta deild, Veikkausliiga, Ireland Premier Division, MLS, Brazil Serie A, J1, K League 1 |
| T2 | Second-tier / strong regional | La Liga 2, Superettan, Ettan North/South, Copa Colombia, Primera B, Liga Pro Ecuador, Canada PL, Ykköseliga, Meistriliiga, Esiliiga A, USL Championship, J2/J3, China Super League |
| T3 | Development / lower | USL League One, MLS Next Pro, Bolivia Liga |

---

## Abbreviations Reference

| Abbreviation | Full form |
|-------------|-----------|
| DNB | Draw No Bet |
| BTS / BTTS | Both Teams Score |
| pp | Percentage points (e.g. gap_pp = difference in hit rate) |
| SM | Sportmonks (the API provider) |
| T1 / T2 / T3 | Tier 1 / Tier 2 / Tier 3 |
| FK | Foreign key (DB join field) |
| emit | Engine generating and logging a pick (emit_log entry) |
| leg | A single market pick within a fixture emission |
| event | A (fixture, market) pair — collapses multi-leg picks per fixture |
| PRX9 | Retired system (V3 ranking layer, not present in V4) |
| 1X2 | Standard three-way market: Home Win / Draw / Away Win |
| alpha team | The favoured side (lower odd) in a fixture |
| promote / PROMOTE | Cell cleared by the stone policy to emit picks |
| PROMOTE_TOLERANCE | Promoted despite borderline statistical confidence |
| MEASURING | Low zone — data collection only, no picks emitted |
| cron | Scheduled daily automation (currently manual — run fetch_upcoming.py daily) |
| emit_log | Table logging every pick the engine has emitted |
| pick_results | Table logging settlement outcome (WIN/VOID/LOSS) after match |
| partition | A (zone, bts_pocket) cell — one row in the classification matrix |
| paper trading | Tracking picks without real money — CSV export for manual tracking |
| chain | (Legacy V3 term) Audit trail — not used in V4 |

---

## SPA Tabs — What Each Shows

### Tab 1: Picks

**API:** `GET /picks?days={n}` + `GET /picks/prx9?days={n}`
**Default window:** 3 days
**Purpose:** All upcoming fixtures in promoted cells — the engine's active output.

Each card shows:
- Fixture (home vs away), league, country, tier badge
- Kickoff date and time (local, converted from UTC)
- Partition key (e.g. `standard:slight_over`)
- Draw zone label
- ★ PROMOTE chip — historical hit rate + n fixtures
- Drift chip (only shown if `watch` or `drifting` — hidden when `stable` or `no_data`)
- Market row(s): market name, pick (alpha team name), odd, `derived` flag if DNB odd was calculated

**Summary bar:** fixtures emitted, picks emitted, window, DNB count, Alpha Win count, unclassifiable skips, not-promoted skips.

**CSV download:** exports current window as paper_trading.csv with operator columns pre-populated blank (sportybet_price, hollywoodbet_price, gbets_price, decision, outcome, notes).

**PRX9 panel:** Retired — always empty.

**Click behaviour:** Clicking a pick card opens the Inspector tab and populates it with that fixture's details.

---

### Tab 2: Upcoming

**API:** `GET /upcoming?days={n}&tier={t}`
**Default window:** 7 days
**Purpose:** All upcoming fixtures with their classification — before the promotion filter. Lets operator see what the engine sees.

Each card shows:
- Fixture, league, tier, kickoff
- 1X2 odds (home/draw/away)
- BTS Yes / No odds
- ★ PROMOTE chip (green) if the cell is in the stone policy, absent otherwise
- Zone group chip (e.g. `standard`)
- BTS v2 chip (e.g. `slight_over`)

**Summary bar:** total fixtures, by tier, promoted count.
**Tier filter:** All / T1 / T2 / T3 dropdown.

---

### Tab 3: Analysis

**API:** `GET /analysis/calibration_partition?min_n={n}` (all tiers) or `GET /analysis/partition_stats_by_tier?min_n={n}` (tier selected)
**Purpose:** Foundation matrix — per-cell hit rates computed live from all settled fixtures in the DB. ★ PROMOTE marks stone policy cells.

Table columns:
- **Zone** — draw zone
- **BTS v2** — BTS pocket
- **n** — settled fixture count in this cell (with complete odds)
- **Hit %** — threeway hit rate (DNB win-or-void / Alpha Win win rate)
- **Avg odd** — average favourite odd in this cell
- **Edge** — hit_rate − 1/avg_odd (positive = profitable edge)
- **Dominant** — pick direction (DNB or Alpha Win)
- **Concentr.** — same as hit % (directional concentration)
- **Tag** — ★ Promote or —

**Note:** If local DB has <min_n settled fixtures with complete odds for a cell, that cell is absent from the table. The `strong:strong_under` cell (stone policy n=33) may appear missing at min_n=30 if local DB has sparse coverage.

---

### Tab 4: Inspector

**API:** `GET /inspector/partition_drift?recent_days={n}`
**Purpose:** Real-time drift monitoring for all 10 promoted cells. Compare recent live performance vs historical stone policy baseline.

Drift table columns:
- **Zone / BTS** — cell identity
- **Historical n** — fixture count in stone policy dataset
- **Hist hit %** — stone policy hit rate
- **Recent n** — settled emits in the drift window
- **Recent hit %** — live hit rate from emit_log
- **Gap pp** — recent − historical (negative = underperforming)
- **Flag** — stable / watch / drifting / no_data

**Click from Picks → Inspector:** Clicking a pick card in the Picks tab also opens the Inspector and shows that fixture's detail card (league, teams, partition key, market/pick/odd).

**Drift window options:** 7d / 14d / 30d (default) / 90d.

---

### Tab 5: Reports

**APIs (4 sub-sections):**
- `GET /reports/settle_activity?days={n}` — settlement activity from `pick_results`
- `GET /reports/emit_performance` — multi-window hit rates from `emit_log` on-the-fly
- `GET /reports/emit_market_breakdown?days={n}` — per-cell hit rates by market
- `GET /reports/emit_recent?days={n}` — per-fixture readback with WIN/VOID/LOSS/PENDING

**Purpose:** Post-match self-evaluation of all emitted picks.

**Settlement activity:** Counts from `pick_results` table. Empty until picks are manually settled. Shows last cron clean run timestamp.

**Multi-window performance:** Computed on-the-fly from `emit_log` joined to `fixtures` scores. Shows performance across 1d / 3d / 7d / 30d / 90d / 180d windows with two views:
- **Legs** — each emit_log row counted separately
- **Events** — (fixture, market) pairs collapsed into one event

**Per-market hit rates:** Settled emits grouped by (zone, bts, market, pick). Requires settled fixtures to have results.

**Recent fixtures readback:** Shows each emitted fixture with WIN/VOID/LOSS/PENDING per leg. PENDING = fixture not yet played or score not yet in DB.

---

### Tab 6: Today

**API:** `GET /diagnostics/today_summary`
**Purpose:** Operator dashboard — single-page health snapshot.

Shows:
- **Cron chip:** fresh (< 26h) / warning (26–48h) / stale (>48h) / never_fired. Cron = the scheduled daily automation that runs fetch + emit. Currently manual.
- **Last clean run chip:** timestamp of last full cron cycle completion
- **Chain chip:** V3 legacy audit chain status — always "unknown" in V4
- **Drift chip:** aggregate drift state across all promoted cells (stable / watch count / drifting count / no_data)
- **Summary metrics:** fixtures kicking off today, fixtures fetched last 24h, picks emitted today, locks pending (always 0 in V4), settled today
- **Engine hit rate blocks:** 7d and 30d event hit rates
- **DB state:** fixtures settled / total, emits settled / total
- **By market today:** DNB count, Alpha Win count for today's emits

---

### Tab 7: Stats

**APIs:** `GET /diagnostics/db_state` + `GET /diagnostics/odds_coverage` + `GET /diagnostics/cron/heartbeat` + `GET /diagnostics/drift_report` + `GET /diagnostics/activity_by_tier?days=7`
**Purpose:** Technical dashboard — DB health, odds data quality, per-tier activity, drift stability table.

Shows:
- **DB counts:** raw row counts for all core tables
- **Cron heartbeat:** last recorded timestamp and stale flag
- **Activity by tier (7d):** emit count by T1 / T2 / T3
- **Odds coverage per league:** % of fixtures with goal odds / BTS odds / corner odds available
- **Drift report:** partition stability table — OK / warning / critical per promoted cell

---

## Current System State (2026-05-23)

| Metric | Value |
|--------|-------|
| DB fixtures total | 32,993 |
| DB fixtures settled | 28,602 |
| DB fixtures upcoming | 4,391 |
| emit_log total | 198 |
| emit settled | 0 (picks all PENDING — upcoming only) |
| pick_results | 0 (no manual settlement yet) |
| Leagues in DB | 57 (30 subscribed + 27 historical) |
| Picks (3d window) | 170 (157 DNB, 13 Alpha Win) |
| Upcoming (7d window) | 391 (184 promoted) |
| ngrok URL | https://steadier-legwarmer-finlike.ngrok-free.dev |
| Port | 8083 |

---

## Known Issues / Fixes Applied This Session

| # | Issue | Status |
|---|-------|--------|
| 1 | 18 subscribed leagues missing from leagues table | Fixed — `update_leagues.py` run (0 inserted, 30 updated) |
| 2 | `fetch_upcoming.py` stored Sportmonks league ID instead of internal DB ID → 1,984 upcoming fixtures untiered in all SPA views | Fixed — DB migrated via SQL UPDATE, script patched to resolve internal ID via `_league_id_map` |
| 3 | July–Aug and Sep–Oct fetch windows hit 20-page cap (1,000 fixtures each) — fixtures beyond cap not fetched | Open — consider sub-window approach or higher cap for dense seasons |
| 4 | Cron never_fired — no scheduled job running | Open — `fetch_upcoming.py` run manually daily |
| 5 | pick_results = 0 — no post-match settlement yet | Expected — Reports performance metrics will populate once upcoming fixtures complete |

---

## How to Operate

### Daily fetch (required)
```powershell
Set-Location C:\OddsFlowV4
python fetch_upcoming.py
```

### Start server
```powershell
Set-Location C:\OddsFlowV4
uvicorn app.main:app --host 0.0.0.0 --port 8083 --reload
```

### Start ngrok (if tunnel needed)
```powershell
ngrok http 8083
```
Fixed URL: `https://steadier-legwarmer-finlike.ngrok-free.dev`

### Access points
- Local SPA: http://localhost:8083
- API docs: http://localhost:8083/docs
- Health: http://localhost:8083/healthz/deep
- Ngrok (public): https://steadier-legwarmer-finlike.ngrok-free.dev
