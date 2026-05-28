# Engine Rules — How Fixtures Are Classified and Picks Are Made

This is the core logic of OddsFlow V3.1. Understanding this file means understanding
what the engine is doing and why.

---

## Step 1 — Draw Zone Classification

Every fixture gets a **draw zone** based on the bookmaker's draw odd.
Source: `zone_of()` in `app/engine/classify.py`.

| Zone | Draw odd range | Meaning |
|------|----------------|---------|
| `strong` | 2.70 – 3.39 | Both teams evenly matched, draw very likely |
| `standard` | 3.40 – 4.09 | Slightly favoured side, draw still plausible |
| `low` | 4.10 – 4.79 | Clear favourite exists, draw less likely |
| `one_sided` | 4.80+ | Strong favourite, draw very unlikely |
| NULL (excluded) | below 2.70 | Too one-sided for this engine, excluded |

---

## Step 2 — DF (Difference Factor) Classification

V3.1 adds DF as a third partition dimension. Source: `df_of()` in `app/engine/classify.py`.

`DF = round(|home_odd − away_odd|)`, clipped to {DF0, DF1, DF2}.

| DF | Condition | Meaning |
|----|-----------|---------|
| `DF0` | diff < 0.5 | Evenly matched within the zone |
| `DF1` | 0.5 ≤ diff < 1.5 | Mild favourite |
| `DF2` | diff ≥ 1.5 | Heavier favourite |

**Why it matters:** DF separates outcomes strongly inside a single zone — alpha_win cells differ
22–26pp across DF tiers; threeway lifts up to 12.6pp from DF0 to DF2. Without DF, V3 was averaging
across heterogeneous fixtures.

---

## Step 3 — BTS Pocket Classification

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

## Step 4 — Cell Assignment

Each fixture lands in exactly one cell: **(zone × DF × bts_pocket)**.
Example: `standard × DF2 × strong_over` — a balanced match with a heavier favourite where both teams are strongly expected to score.

The combinatorial space is 4 zones × 3 DF × 4 pockets = **48 possible cells**, but only **20** are active in V3.1 (filtered by `min_n` and PASS/MARGINAL/FLAG status).

---

## Step 5 — V3.1 Active Cells

Locked from the 28,425-fixture calibration + 2026-05-27 DF separation analysis.
Source: `app/engine/static_policy.py::V3_ACTIVE`.

### Strong zone — 6 cells — fires `goals_nl` (Over 1.5 Goals)

| Cell | n | gn_hit |
|------|---|--------|
| strong:DF0:slight_over | 704 | 70.9% |
| strong:DF0:slight_under | 851 | 65.2% |
| strong:DF1:slight_over | 3,712 | 72.6% |
| strong:DF1:slight_under | 2,525 | 66.7% |
| strong:DF2:slight_over | 581 | 71.4% |
| strong:DF2:slight_under | 2,549 | 67.1% |

### Standard zone — 7 cells — fires `goals_nl` + `corners_nl` (Over 8.5 Corners)

| Cell | n | gn_hit | cn_hit |
|------|---|--------|--------|
| standard:DF0:slight_over | 186 | 80.1% | 61.9% |
| standard:DF0:strong_over | 90 | 81.1% | 61.3% |
| standard:DF1:slight_over | 4,134 | 79.7% | 65.4% |
| standard:DF1:strong_over | 1,034 | 83.5% | 69.7% |
| standard:DF2:slight_over | 5,129 | 76.9% | 63.9% |
| standard:DF2:slight_under | 1,939 | 71.6% | 57.9% |
| standard:DF2:strong_over | 195 | 86.2% | 74.6% |

### Low zone — 3 cells — fires `dnb` (alpha-win-or-draw)

| Cell | n | threeway_hit |
|------|---|--------------|
| low:DF2:slight_over | 1,733 | 84.9% |
| low:DF2:slight_under | 675 | 91.6% |
| low:DF2:strong_over | 238 | 82.8% |

### One-sided zone — 4 cells — fires `alpha_win`

| Cell | n | threeway_hit |
|------|---|--------------|
| one_sided:DF2:slight_over | 1,119 | 76.6% |
| one_sided:DF2:slight_under | 814 | 81.0% |
| one_sided:DF2:strong_over | 66 | 66.7% (FLAG) |
| one_sided:DF2:strong_under | 47 | 80.9% (`min_n` lowered 50→45) |

---

## Step 6 — Foundation Matrix (display only)

Separate from V3.1 pick firing. `compute_foundation()` in `app/engine/promotion.py` runs across
all settled fixtures to surface live hit rates per cell at `/api/foundation` for the Analysis tab.
It uses an older PROMOTE/PROMOTE_TOLERANCE/HOLD/NO classification with `LOW_ZONE_SUPPRESS = True`,
so the display shows low cells as `MEASURING` even though pick firing has them active.

This is intentional — the matrix is for analysis, V3.1 is for emission.

---

## Step 7 — Pick Generation

For each upcoming fixture in window `days`:

1. Classify → (zone, df, bts_pocket).
2. Look up the cell in `V3_ACTIVE`. Skip if not present (counts toward `partition_not_promoted`).
3. For each market in the cell config:
   - **goals_nl:** label `"Over 1.5 Goals"`, `pick_odd` from `fixtures.goals_over_15_odd` (often NULL — by design).
   - **corners_nl:** label `"Over 8.5 Corners"`, `pick_odd` from `fixtures.corners_over_85_odd` (almost always NULL — by design).
   - **dnb:** label = alpha team name, `pick_odd` derived from 1X2 via `(1 − p_draw) / p_alpha`.
   - **alpha_win:** label = alpha team name, `pick_odd = min(home_odd, away_odd)`.
4. Compute drift flag from recent emit_log outcomes vs historical baseline (`stable` / `watch` / `drifting` / `no_data`).
5. Write to `emit_log` via `write_emit_log()`, which:
   - Deletes any prior unsettled pick on the same (fixture_id, market) with a different `pick_uuid` (supersede on alpha team change).
   - `INSERT OR IGNORE` the new row.

Each pick is stored with a SHA-256 `pick_uuid` derived from `{fixture_id}:{market}:{pick}` for idempotence.

---

## Step 8 — Settlement

`settle.py` runs after `fetch_results.py`. For each pending emit_log row whose fixture has a score:

| Market | Outcome rule |
|--------|--------------|
| `goals_nl` | `total_goals > 1.5` → WIN, else LOSS |
| `corners_nl` | `total_corners > 8.5` → WIN, else LOSS (skipped if `fixture_stats.total_corners` is NULL) |
| `dnb` | Alpha wins → WIN; draw → VOID (stake returned, 0.5); alpha loses → LOSS |
| `alpha_win` | Alpha wins → WIN; draw or alpha loses → LOSS |

Results written to `pick_results` with `outcome` (string label) and `actual_value` (float 1.0 / 0.5 / 0.0).

---

## Hit-rate convention (V3)

The non-loss convention is used: `hit_rate = (wins + voids) / settled`.
Voids count as wins because stake is returned. This restores the V3 reporting standard
(Wilson-style proper-fraction was reverted in Session 16).

---

## Drift

Per (zone, df, bts_pocket, market) cell, compare recent emit_log hit rate to historical baseline:

| Flag | Condition |
|------|-----------|
| `stable` | gap > −5pp |
| `watch` | −10pp < gap ≤ −5pp |
| `drifting` | gap ≤ −10pp |
| `no_data` | fewer than 10 settled emits in window (default 30d) |

Drift is informational. The engine does NOT auto-demote drifting cells — operator reviews and decides.
