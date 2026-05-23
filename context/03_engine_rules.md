# Engine Rules — How Fixtures Are Classified and Picks Are Made

This is the core logic of OddsFlow. Understanding this file means understanding
what the engine is doing and why.

---

## Step 1 — Draw Zone Classification

Every fixture gets a **draw zone** based on the bookmaker's draw odd.

| Zone | Draw odd range | Meaning |
|------|----------------|---------|
| `strong` | 2.70 – 3.39 | Both teams evenly matched, draw very likely |
| `standard` | 3.40 – 4.09 | Slightly favoured side, draw still plausible |
| `low` | 4.10 – 4.79 | Clear favourite exists, draw less likely |
| `one_sided` | 4.80+ | Strong favourite, draw very unlikely |
| NULL (excluded) | below 2.70 | Too draw-heavy, excluded from analysis |

**Why this matters:** Each zone behaves differently for goals and corners totals.
Strong-draw games tend to be low-scoring. One-sided games tend to have more action.

---

## Step 2 — BTS Pocket Classification

Every fixture also gets a **BTS pocket** based on Both-Teams-To-Score odds.
The threshold is **1.50** — if either side's odds are below 1.50, it's "strong".

| Pocket | Condition |
|--------|-----------|
| `strong_over` | BTTS Yes favoured AND yes_odd < 1.50 |
| `slight_over` | BTTS Yes favoured AND yes_odd ≥ 1.50 |
| `slight_under` | BTTS No favoured AND no_odd ≥ 1.50 |
| `strong_under` | BTTS No favoured AND no_odd < 1.50 |

"Yes favoured" = yes_odd ≤ no_odd.

**Why this matters:** How likely both teams score affects whether goals lines hit.
`strong_over` cells tend to have higher over-goals rates.

---

## Step 3 — Cell Assignment

Each fixture lands in exactly one cell: **(zone × bts_pocket)**.
Example: `standard × strong_over` — a balanced match where both teams are
strongly expected to score.

There are 4 zones × 4 pockets = **16 possible cells**.

---

## Step 4 — Half-Lines (what we're betting)

Instead of whole-number totals, we use **half-lines** (Asian handicap style).
A half-line has no draw — the result is always WIN or LOSE.

| Zone | Goals lines | Corners lines |
|------|-------------|---------------|
| strong / standard | Natural: 1.5 / System: 2.5 | Natural: 7.5 / System: 8.5 |
| low / one_sided | Natural: 2.5 / System: 3.5 | Natural: 8.5 / System: 9.5 |

**Natural line** = lower line (higher hit rate, lower odds).
**System line** = 1-up from natural (lower hit rate, better odds).
**Drop** = how much the hit rate falls between natural and system.

---

## Step 5 — Foundation Matrix (historical hit rates)

For each cell, we count settled fixtures and calculate:
- `gn_hit` — % of fixtures where total goals > natural line
- `gs_hit` — % where total goals > system line
- `cn_hit` — % where total corners > natural line
- `cs_hit` — % where total corners > system line
- `threeway_hit` — % where DNB (alpha win or draw) / alpha win lands

The Foundation Matrix shows this grid for three slices:
- `all` — all leagues combined
- `t1` — Tier 1 only
- `t2t3` — Tier 2 and 3 combined

---

## Step 6 — Promotion Decision

A cell gets **PROMOTE** status when its hit rate is strong enough to bet.

| Status | Meaning |
|--------|---------|
| `PROMOTE` | Hit rate ≥ 72% — bet this cell |
| `PROMOTE_TOLERANCE` | Hit rate 67.5–71.9% AND drop rank qualifies |
| `HOLD` | In tolerance band but drop rank doesn't qualify |
| `NO` | Hit rate below 67.5% |
| `MEASURING` | Would be PROMOTE but in `low` zone (suppressed until more data) |

**Drop rank:** Within each zone, cells are ranked by how much the hit rate
drops from natural to system line. Rank 1 = least drop = most consistent.
A secondary cell (rank 2+) only qualifies for PROMOTE_TOLERANCE if its drop
is within 4.5 percentage points of rank 1.

**Low zone suppression:** `low` zone cells are suppressed to MEASURING even
if they hit the threshold — they need more calibration data.

---

## Step 7 — Pick Generation

For fixtures in promoted cells, we emit picks:
- **Goals:** "Over {natural_line}" for the fixture's zone
- **Corners:** "Over {natural_line}" for corners
- **DNB:** "Alpha Win or Draw" (strong/standard zones) or "Alpha Win" (low/one_sided)
- **Alpha Win:** Favourite to win outright (EV layer)

Each pick is stored in `emit_log` with a chain hash for integrity.

---

## V4 pick markets

| Zone | Market fired | Logic |
|------|-------------|-------|
| `strong` / `standard` | DNB | Alpha Win OR Draw — derived odd from 1X2 |
| `one_sided` | Alpha Win | Favourite to win outright |
| `low` | NONE | Suppressed — measuring only |

Goals and corners picks are retired in V4.
