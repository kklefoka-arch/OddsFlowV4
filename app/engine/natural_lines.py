"""OddsFlow V3 — Natural and system half-lines per zone/market.

Half-lines are 2-state only: total > line = GREEN, total ≤ line = RED.
Each zone maps to (natural_line, system_line) per market.
"""

from __future__ import annotations

# (natural_line, system_line) per zone per market.
# Re-Foundation (2026-05-30): natural lines revised from the line sweep
# (Output/NATURAL_LINE_SWEEP_2026-05-30.md). Natural goals = O1.5 in ALL zones
# (the old escalating O2.5 for low/one_sided was disproven); natural corners =
# O7.5 strong / O8.5 elsewhere. system_line is the 1-up (advanced Mean config).
HALF_LINES: dict[str, dict[str, tuple[float, float]]] = {
    "strong":    {"goals": (1.5, 2.5), "corners": (7.5, 8.5)},
    "standard":  {"goals": (1.5, 2.5), "corners": (8.5, 9.5)},
    "low":       {"goals": (1.5, 2.5), "corners": (8.5, 9.5)},
    "one_sided": {"goals": (1.5, 2.5), "corners": (8.5, 9.5)},
}

ZONES: tuple[str, ...] = ("strong", "standard", "low", "one_sided")

BTS_POCKETS: tuple[str, ...] = (
    "strong_over",
    "slight_over",
    "slight_under",
    "strong_under",
)


def natural_line(zone: str, market: str) -> float:
    """Return the natural (lower) half-line for a zone/market pair.

    Args:
        zone:   One of ZONES.
        market: "goals" or "corners".

    Returns:
        The natural line float.

    Raises:
        KeyError: If zone or market is not found in HALF_LINES.
    """
    return HALF_LINES[zone][market][0]


def system_line(zone: str, market: str) -> float:
    """Return the system (upper, 1-up) half-line for a zone/market pair.

    Args:
        zone:   One of ZONES.
        market: "goals" or "corners".

    Returns:
        The system line float.

    Raises:
        KeyError: If zone or market is not found in HALF_LINES.
    """
    return HALF_LINES[zone][market][1]
