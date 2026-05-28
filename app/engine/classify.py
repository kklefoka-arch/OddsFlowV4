"""OddsFlow V4 — Fixture classification.

Maps draw_odd → draw_zone and (btts_yes_odd, btts_no_odd) → bts_pocket.
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


def classify_fixture(row: dict) -> dict:
    """Derive zone, bts_pocket, and tier from a fixture dict.

    Reads keys: draw_odd, btts_yes_odd, btts_no_odd, tier.

    Args:
        row: Mapping containing fixture odds and tier fields.

    Returns:
        Dict with keys ``zone``, ``bts_pocket``, ``tier``.
    """
    return {
        "zone": zone_of(row.get("draw_odd")),
        "bts_pocket": bts_of(row.get("btts_yes_odd"), row.get("btts_no_odd")),
        "tier": row.get("tier"),
    }
