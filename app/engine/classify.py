"""OddsFlow V4 — Fixture classification.

Maps draw_odd → draw_zone, (btts_yes_odd, btts_no_odd) → bts_pocket,
and (home_odd, away_odd) → df (Difference Factor, V3.1).
"""

from __future__ import annotations


def zone_of(draw_odd: float | None) -> str | None:
    """Classify a draw odd into a draw zone.

    Zones:
        strong    2.70 ≤ odd < 3.40
        standard  3.40 ≤ odd < 4.10
        low       4.10 ≤ odd < 4.80
        one_sided odd ≥ 4.80
        NULL      odd < 2.70  (excluded from analysis)

    Args:
        draw_odd: The bookmaker draw odd.

    Returns:
        Zone string, or None when the fixture is excluded (draw_odd < 2.70
        or draw_odd is None).
    """
    if draw_odd is None:
        return None
    if draw_odd < 2.70:
        return None          # excluded
    if draw_odd < 3.40:
        return "strong"
    if draw_odd < 4.10:
        return "standard"
    if draw_odd < 4.80:
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


def df_of(home_odd: float | None, away_odd: float | None) -> str | None:
    """Classify Difference Factor (DF) from rounded home/away odds.

    DF buckets (V3.1, enhancement 2026-05-27):
        DF0  diff == 0   (evenly matched odds)
        DF1  diff == 1
        DF2  diff >= 2   (heavy favourite)

    Rule: diff = abs(round(home_odd) - round(away_odd)).

    Args:
        home_odd: Bookmaker home odd.
        away_odd: Bookmaker away odd.

    Returns:
        DF bucket string, or None if either odd is missing.
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
    """Derive zone, bts_pocket, df, and tier from a fixture dict.

    Reads keys: draw_odd, btts_yes_odd, btts_no_odd, home_odd, away_odd, tier.

    Args:
        row: Mapping containing fixture odds and tier fields.

    Returns:
        Dict with keys ``zone``, ``bts_pocket``, ``df``, ``tier``.
    """
    return {
        "zone": zone_of(row.get("draw_odd")),
        "bts_pocket": bts_of(row.get("btts_yes_odd"), row.get("btts_no_odd")),
        "df": df_of(row.get("home_odd"), row.get("away_odd")),
        "tier": row.get("tier"),
    }
