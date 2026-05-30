"""OddsFlow V4 — Fixture classification.

Maps draw_odd → draw_zone, BTTS odds → bts (yes/no) + spread signal,
and (home_odd, away_odd) → DF bucket.

v4 (2026-05-30) — the partition is the PURE form ``(zone, bts)`` where
``bts ∈ {over, under}`` (8 cells). The BTS strong/slight **spread**, **DF**, and
the **H2H-corner** count are SIGNALS, not cell axes (validated by the fresh test
+ feasibility workflow). ``bts_of`` (the legacy 4-pocket) is kept for display /
back-compat only. No Wilson, no EV anywhere in this module.
"""

from __future__ import annotations


def zone_of(draw_odd: float | None) -> str | None:
    """Classify a draw odd into a draw zone.

    Boundaries (raw-notes overlay, Session 19 — 2026-05-28):
        excluded   odd < 2.90  (both_sided — too draw-heavy, not in policy)
        strong     2.90 ≤ odd < 3.30
        standard   3.30 ≤ odd < 3.80
        low        3.80 ≤ odd < 4.30
        one_sided  odd ≥ 4.30

    Why these boundaries: under the prior V3 cutoffs (2.70/3.40/4.10/4.80),
    one_sided fixtures crept into the low bucket, contaminating low-zone
    hit rates around 50% across all markets. Pulling one_sided's floor down
    to 4.30 keeps the low bucket clean (3.80–4.30) and reduces standard-zone
    bleed at the bottom edge.

    Args:
        draw_odd: The bookmaker draw odd.

    Returns:
        Zone string, or None when the fixture is excluded (draw_odd < 2.90
        or draw_odd is None).
    """
    if draw_odd is None:
        return None
    if draw_odd < 2.90:
        return None          # excluded (both_sided)
    if draw_odd < 3.30:
        return "strong"
    if draw_odd < 3.80:
        return "standard"
    if draw_odd < 4.30:
        return "low"
    return "one_sided"


def bts_of(yes_odd: float | None, no_odd: float | None) -> str | None:
    """Classify BTS (both-teams-score) odds into a pocket label.

    Classification (threshold 1.50):
        strong_over   yes favoured AND yes_odd < 1.50
        slight_over   yes favoured AND yes_odd ≥ 1.50
        strong_under  no favoured  AND no_odd  < 1.50
        slight_under  no favoured  AND no_odd  ≥ 1.50

    "Yes favoured" means yes_odd ≤ no_odd.

    Args:
        yes_odd: Bookmaker odd for BTTS Yes.
        no_odd:  Bookmaker odd for BTTS No.

    Returns:
        BTS pocket string, or None if either odd is missing.
    """
    if yes_odd is None or no_odd is None:
        return None

    yes_favoured = yes_odd <= no_odd

    if yes_favoured:
        return "strong_over" if yes_odd < 1.50 else "slight_over"
    else:
        return "strong_under" if no_odd < 1.50 else "slight_under"


def bts_yesno(yes_odd: float | None, no_odd: float | None) -> str | None:
    """v4 cell axis — pure BTS direction.

        over   yes favoured (yes_odd ≤ no_odd) — both teams expected to score
        under  no favoured

    Returns None if either odd is missing.
    """
    if yes_odd is None or no_odd is None:
        return None
    return "over" if yes_odd <= no_odd else "under"


def bts_spread(yes_odd: float | None, no_odd: float | None) -> str | None:
    """v4 SIGNAL — how heavily the favoured BTS side is priced (threshold 1.50).

        strong  favoured side < 1.50
        slight  favoured side ≥ 1.50

    Used as a confidence chip and the one goals-override (standard:over / low:over
    fire goals at the strong rate when spread == strong). NOT a cell axis.
    """
    if yes_odd is None or no_odd is None:
        return None
    return "strong" if min(yes_odd, no_odd) < 1.50 else "slight"


def df_of(home_odd: float | None, away_odd: float | None) -> str | None:
    """Classify the home/away odds spread into a DF bucket.

    DF = |round(home_odd) - round(away_odd)|, bucketed:
        DF0  diff == 0  (very even)
        DF1  diff == 1  (mild edge)
        DF2  diff >= 2  (clear edge)

    Returns None if either odd is missing.
    """
    if home_odd is None or away_odd is None:
        return None
    diff = abs(round(home_odd) - round(away_odd))
    if diff == 0:
        return "DF0"
    if diff == 1:
        return "DF1"
    return "DF2"


def classify_fixture(row: dict) -> dict:
    """Derive zone, bts (yes/no cell axis), spread+df signals, and tier.

    Reads keys: draw_odd, home_odd, away_odd, btts_yes_odd, btts_no_odd, tier.

    Returns dict with keys:
        ``zone``       — cell axis (draw zone)
        ``bts``        — cell axis (over/under) — the v4 BTS direction
        ``spread``     — SIGNAL (strong/slight)
        ``df``         — SIGNAL (DF0/DF1/DF2)
        ``bts_pocket`` — legacy 4-pocket, for display/back-compat only
        ``tier``
    """
    y, n = row.get("btts_yes_odd"), row.get("btts_no_odd")
    return {
        "zone": zone_of(row.get("draw_odd")),
        "bts": bts_yesno(y, n),
        "spread": bts_spread(y, n),
        "df": df_of(row.get("home_odd"), row.get("away_odd")),
        "bts_pocket": bts_of(y, n),
        "tier": row.get("tier"),
    }
