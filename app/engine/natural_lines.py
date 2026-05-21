"""OddsFlow V3 — Natural and system half-lines per zone/market.

Half-lines are 2-state only: total > line = GREEN, total ≤ line = RED.
Each zone maps to (natural_line, system_line) per market.
"""

from __future__ import annotations

# (natural_line, system_line) per zone per market
HALF_LINES: dict[str, dict[str, tuple[float, float]]] = {
    "strong":    {"goals": (1.5, 2.5), "corners": (7.5, 8.5)},
    "standard":  {"goals": (1.5, 2.5), "corners": (7.5, 8.5)},
    "low":       {"goals": (2.5, 3.5), "corners": (8.5, 9.5)},
    "one_sided": {"goals": (2.5, 3.5), "corners": (8.5, 9.5)},
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
