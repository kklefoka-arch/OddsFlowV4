# Engine Rules — How Fixtures Are Classified and Picks Are Made (V3)

This is the core logic of OddsFlow V4 as restored to V3 in Session 19.
The structured edge lives in `(draw_zone × bts_pocket)` — the parent
combination of the bookmaker's draw price and BTS market sentiment.
Hit rate is the only edge metric. No EV. No DF as a partition key.

---

## Step 1 — Draw Zone Classification

Every fixture gets a **draw zone** based on the bookmaker's draw odd.
Source: `zone_of()` in `app/engine/classify.py`.

**Boundaries (raw-notes overlay, Session 19 — 2026-05-28):**

| Zone | Draw odd range | Notes |
|------|----------------|-------|
| (excluded) | `< 2.90` | both_sided — too draw-heavy, not in policy |
| `strong` | `2.90 ≤ x < 3.30` | Both teams evenly matched, draw very likely |
| `standard` | `3.30 ≤ x < 3.80` | Slightly favoured side, draw still plausible — the cleanest cell |
| `low` | `3.80 ≤ x < 4.30` | Clear favourite exists, draw less likely |
| `one_sided` | `≥ 4.30` | Strong favourite, draw very unlikely |

**Why these cutoffs:** the original V3 boundaries (2.70 / 3.40 / 4.10 / 4.80) let one_sided fixtures creep into the low bucket, contaminating low-zone hit rates around 50% across all markets and bleeding into the standard zone too. The raw-notes overlay tightens each band so each zone captures a structurally distinct fixture type.

---

## Step 2 — BTS Pocket Classification

Every fixture also gets a **BTS pocket** from Both-Teams-To-Score odds.
Source: `bts_of()` in `app/engine/classify.py`. Threshold is **1.50**.

| Pocket | Condition |
|--------|-----------|
| `strong_over` | BTTS Yes favoured AND `yes_odd < 1.50` |
| `slight_over` | BTTS Yes favoured AND `yes_odd ≥ 1.50` |
| `slight_under` | BTTS No favoured AND `no_odd ≥ 1.50` |
| `strong_under` | BTTS No favoured AND `no_odd < 1.50` |

"Yes favoured" = `yes_odd ≤ no_odd`.

---

## Step 3 — Cell Assignment

Each fixture lands in exactly one cell: **(zone × bts_pocket)**.
4 zones × 4 pockets = 16 possible cells, **9 active** in V3.

---

## Step 4 — V3 Active Cells (9)

Locked from 28,425-fixture analysis. Source: `app/engine/static_policy.py::V3_ACTIVE`.

| Cell | Markets | Reference hit (pre-overlay) | n |
|------|---------|---------------------------|---|
| strong:slight_over | goals_nl (Over 1.5) + DNB | gn 72.2%, threeway 70.5% | 4,997 |
| strong:slight_under | goals_nl + DNB | gn 66.6%, threeway 74.9% | 5,925 |
| standard:slight_over | goals_nl + corners_nl + DNB | gn 78.2%, cn 64.5%, threeway 74.8% | 9,449 |
| standard:strong_over | goals_nl + corners_nl + DNB | gn 83.7%, cn 69.9%, threeway 69.4% | 1,319 |
| standard:slight_under | goals_nl + corners_nl + DNB | gn 71.6%, cn 57.8%, threeway 82.8% (MARGINAL) | 1,940 |
| low:slight_over | DNB | threeway 84.9% | 1,733 |
| low:slight_under | DNB | threeway 91.6% | 675 |
| one_sided:slight_over | alpha_win | threeway 76.6% | 1,119 |
| one_sided:slight_under | alpha_win | threeway 81.0% | 814 |

**Important:** the hit-rate numbers above were computed against the *prior* zone boundaries. They remain in `V3_MARKETS` as reference only. The next 6 weeks of live settlement under the Session-19 boundaries will produce a recalibration baseline. Don't gate emission on these numbers.

---

## Step 5 — Foundation Matrix (display only)

Separate from V3 pick firing. `compute_foundation()` in `app/engine/promotion.py` runs across all settled fixtures and surfaces live hit rates per cell at `/api/foundation` for the Analysis tab. It uses its own PROMOTE / PROMOTE_TOLERANCE / HOLD / NO classification and sets `LOW_ZONE_SUPPRESS = True` for display — so low cells appear as `MEASURING` in the matrix even though pick firing has them active. This is intentional: the matrix is for analysis, V3 is for emission.

---

## Step 6 — Pick Generation

For each upcoming fixture in window `days`:

1. Classify → (zone, bts_pocket).
2. Look up the cell in `V3_ACTIVE`. Skip if not present (counts toward `partition_not_promoted`).
3. For each market in the cell config:
   - **goals_nl:** label `"Over 1.5 Goals"`, `pick_odd` from `fixtures.goals_over_15_odd` (often NULL — by design).
   - **corners_nl:** label `"Over 8.5 Corners"`, `pick_odd` from `fixtures.corners_over_85_odd` (almost always NULL — by design).
   - **dnb:** label = alpha team name, `pick_odd` derived from 1X2 via `(1 − p_draw) / p_alpha`.
   - **alpha_win:** label = alpha team name, `pick_odd = min(home_odd, away_odd)`.
4. Compute drift flag from recent emit_log outcomes vs historical baseline (`stable` / `watch` / `drifting` / `no_data`). V3 non-loss convention.
5. Write to `emit_log` via `write_emit_log()` — supersedes stale unsettled pick on the same `(fixture_id, market)` when alpha label changed, then `INSERT OR IGNORE` on `pick_uuid`.

`pick_uuid = sha256("{fixture_id}:{market}:{pick}")[:36]`.

---

## Step 7 — Settlement

`settle.py` runs after `fetch_results.py`. For each pending emit_log row whose fixture has a score:

| Market | Outcome rule |
|--------|--------------|
| `goals_nl` | `total_goals > 1.5` → WIN, else LOSS |
| `corners_nl` | `total_corners > 8.5` → WIN, else LOSS (skipped if `fixture_stats.total_corners` is NULL) |
| `dnb` | alpha wins → WIN (1.0); draw → VOID (0.5); alpha loses → LOSS (0.0) |
| `alpha_win` | alpha wins → WIN; else LOSS |

Writes `pick_results(outcome, actual_value)` plus a `settle` heartbeat to `system_health`.

---

## Hit-rate convention

V3 non-loss: `hit_rate = (wins + voids) / settled`. Voids count as wins (stake returned).
This is the only edge metric the live engine reports — by Durable Rule 2 (no EV, no Wilson, no economic gating).

---

## Drift

Per (zone, bts_pocket, market) cell, compare recent emit_log hit rate to historical baseline.

| Flag | Condition |
|------|-----------|
| `stable` | gap > −5pp |
| `watch` | −10pp < gap ≤ −5pp |
| `drifting` | gap ≤ −10pp |
| `no_data` | recent_n < 10 |

Drift is informational. The engine never auto-demotes — operator reviews and decides.

---

## What does NOT exist (by Durable Rule)

- **DF as a partition key** — `df_of()` was removed in Session 19. DF lives only in the analysis folder as a signal. Re-introduction requires 6 weeks of post-overlay V3 settlement first.
- **EV / breakeven / Wilson** — analysis-only. No code path in the live engine consults these.
- **Goals or corners system line picks** — natural line only. System line is a foundation metric, not a pick market.
- **Team form / position / predicted-uncertainty weighting** — odds drivers + H2H corner counts are the only valid signals.
- **PRX9 layer** — retired with V3.
- **Effective-line fallback for goals_nl / corners_nl** — explicit V3 decision. `pick_odd` NULL is the expected state for most of these picks.
