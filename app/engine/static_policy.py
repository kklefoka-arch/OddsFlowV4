"""OddsFlow Ground-Zero Policy — 2-key (zone, bts_pocket)
========================================================
Re-Foundation (2026-05-30). Reverts the Session 23c DF-as-partition decision:
the partition is again 2-key ``(zone, bts_pocket)``. DF and the H2H-corner count
are SIGNALS (qualifying filters / confidence context), NOT partition axes — see
``signals`` / ``gates`` per cell, enforced in routes_picks / settle.

Drawn from the re-run deep test (Phase 1, ``Output/GROUND_ZERO_TEST_2026-05-30.md``;
policy ``Output/ground_zero_policy_FINAL_2026-05-30.txt``), 28,539 settled fixtures,
Session-19 boundaries. Hit-rate only — NO Wilson, NO EV, NO regression.

Natural lines (revised, evidence-based via Scripts/sweep_natural_lines.py):
  goals    O1.5 in ALL zones        (goals_over_15_odd)
  corners  O7.5 strong / O8.5 rest  (corners_over_75/85_odd)
  threeway alpha-or-draw ALL zones   (a draw is a protected WIN — NO 0.5 void)
Straight-win (alpha-only) is NOT a ground-zero market; it lives in the advanced
Optimistic three-picks-log config.

No n-based exclusion (operator decision): every (zone,bts) cell with data promotes.
Cells with n<45 carry ``provisional`` and are confirmed/killed by live drift.

PROMOTED_CELLS — display + inspector metadata, 2-key.
V3_MARKETS     — per-cell pick configuration consumed by routes_picks.
V3_ACTIVE      — alias of V3_MARKETS (kept for route compatibility).
"""
from __future__ import annotations

from typing import Any

LOW_ZONE_SUPPRESS: bool = False   # low zone is among the strongest under revised lines

_GL15 = "goals_over_15_odd"
_CL75 = "corners_over_75_odd"
_CL85 = "corners_over_85_odd"

_AOD = "alpha_or_draw"            # 3-way ground-zero pick: favourite wins OR draw -> WIN


# ---------------------------------------------------------------------------
# V3_MARKETS — 2-key (zone, bts_pocket). Markets: goals_nl | corners_nl | threeway.
# Fields: line (float|None), hit (float), n (int), odd_col (str|None),
#         optional provisional (bool).
# Per-cell "signals" = display context; "gates" = HARD suppression rules:
#   gates["cell_suppress_df"]    -> list of DF buckets that suppress the whole cell
#   gates["corners_suppress_h2h"]-> list of h2h-corner values that suppress corners_nl
# ---------------------------------------------------------------------------
V3_MARKETS: dict[tuple[str, str], dict[str, Any]] = {

    # -- strong (corners natural O7.5) -------------------------------------
    ("strong", "slight_over"): {
        "goals_nl":   {"line": 1.5, "hit": 71.7, "n": 2935, "odd_col": _GL15},
        "corners_nl": {"line": 7.5, "hit": 69.7, "n": 2278, "odd_col": _CL75},
        "threeway":   {"line": None, "pick": _AOD, "hit": 69.4, "n": 2935, "odd_col": None},
    },
    ("strong", "slight_under"): {
        "goals_nl":   {"line": 1.5, "hit": 66.8, "n": 4798, "odd_col": _GL15},
        "corners_nl": {"line": 7.5, "hit": 67.6, "n": 3245, "odd_col": _CL75},
        "threeway":   {"line": None, "pick": _AOD, "hit": 74.3, "n": 4798, "odd_col": None},
    },
    ("strong", "strong_under"): {
        "goals_nl":   {"line": 1.5, "hit": 50.0, "n": 16, "odd_col": _GL15},
        "corners_nl": {"line": 7.5, "hit": 71.4, "n": 14, "odd_col": _CL75, "provisional": True},
        "threeway":   {"line": None, "pick": _AOD, "hit": 93.8, "n": 16, "odd_col": None},
        "provisional": True,
    },

    # -- standard (corners natural O8.5) -----------------------------------
    ("standard", "strong_over"): {
        "goals_nl":   {"line": 1.5, "hit": 83.8, "n": 875, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 68.3, "n": 758, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 67.3, "n": 875, "odd_col": None},
        "gates": {"cell_suppress_df": ["DF0"], "corners_suppress_h2h": ["under"]},
    },
    ("standard", "slight_over"): {
        "goals_nl":   {"line": 1.5, "hit": 76.8, "n": 10106, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 63.6, "n": 7620, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 73.1, "n": 10106, "odd_col": None},
    },
    ("standard", "slight_under"): {
        "goals_nl":   {"line": 1.5, "hit": 71.7, "n": 2042, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 56.8, "n": 1404, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 81.5, "n": 2042, "odd_col": None},
        "gates": {"corners_suppress_h2h": ["under"]},
    },
    ("standard", "strong_under"): {
        "goals_nl":   {"line": 1.5, "hit": 73.7, "n": 19, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 12.5, "n": 8, "odd_col": _CL85, "provisional": True},
        "threeway":   {"line": None, "pick": _AOD, "hit": 84.2, "n": 19, "odd_col": None},
        "provisional": True,
    },

    # -- low (corners natural O8.5; clear favourite + draw protection) -----
    ("low", "strong_over"): {
        "goals_nl":   {"line": 1.5, "hit": 85.0, "n": 642, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 71.3, "n": 606, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 74.0, "n": 642, "odd_col": None},
        "gates": {"corners_suppress_h2h": ["under"]},
    },
    ("low", "slight_over"): {
        "goals_nl":   {"line": 1.5, "hit": 79.7, "n": 2502, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 64.8, "n": 2134, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 81.4, "n": 2502, "odd_col": None},
    },
    ("low", "slight_under"): {
        "goals_nl":   {"line": 1.5, "hit": 71.4, "n": 783, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 55.8, "n": 557, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 88.6, "n": 783, "odd_col": None},
        "gates": {"corners_suppress_h2h": ["under"]},
    },
    ("low", "strong_under"): {
        "goals_nl":   {"line": 1.5, "hit": 55.6, "n": 18, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 42.9, "n": 7, "odd_col": _CL85, "provisional": True},
        "threeway":   {"line": None, "pick": _AOD, "hit": 77.8, "n": 18, "odd_col": None},
        "provisional": True,
    },

    # -- one_sided (corners natural O8.5; draw protection still wins) -------
    ("one_sided", "strong_over"): {
        "goals_nl":   {"line": 1.5, "hit": 89.2, "n": 212, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 66.2, "n": 204, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 81.6, "n": 212, "odd_col": None},
    },
    ("one_sided", "slight_over"): {
        "goals_nl":   {"line": 1.5, "hit": 83.9, "n": 2218, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 69.1, "n": 2075, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 88.7, "n": 2218, "odd_col": None},
    },
    ("one_sided", "slight_under"): {
        "goals_nl":   {"line": 1.5, "hit": 82.8, "n": 1307, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 65.6, "n": 1146, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 94.2, "n": 1307, "odd_col": None},
    },
    ("one_sided", "strong_under"): {
        # corners excluded: coverage n=29 < 30 -> not enough to even baseline
        "goals_nl":   {"line": 1.5, "hit": 72.7, "n": 66, "odd_col": _GL15},
        "threeway":   {"line": None, "pick": _AOD, "hit": 97.0, "n": 66, "odd_col": None},
        "provisional": True,
    },
}

# Active pick set (alias; low zone stays active).
V3_ACTIVE: dict[tuple[str, str], dict[str, Any]] = {
    k: v for k, v in V3_MARKETS.items()
    if not (LOW_ZONE_SUPPRESS and k[0] == "low")
}


def _threeway_hit(cell: dict[str, Any]) -> float:
    tw = cell.get("threeway")
    return tw["hit"] if tw else 0.0


def _composite(cell: dict[str, Any]) -> float:
    """Mean of the cell's market hit-rates (display headline)."""
    hits = [m["hit"] for k, m in cell.items()
            if isinstance(m, dict) and "hit" in m and k in ("goals_nl", "corners_nl", "threeway")]
    return round(sum(hits) / len(hits), 1) if hits else 0.0


# ---------------------------------------------------------------------------
# PROMOTED_CELLS — display + inspector metadata (2-key).
# Required fields: zone, bts_pocket, threeway_hit, threeway_pick, gn_hit, cn_hit,
#   n_fixtures, cell_promoted, promote_status, composite, provisional.
# ---------------------------------------------------------------------------
PROMOTED_CELLS: dict[tuple[str, str], dict[str, Any]] = {}
for (_z, _b), _cell in V3_ACTIVE.items():
    _gn = _cell.get("goals_nl")
    _cn = _cell.get("corners_nl")
    _tw = _cell.get("threeway")
    PROMOTED_CELLS[(_z, _b)] = {
        "zone": _z, "bts_pocket": _b,
        "cell_promoted": True,
        "threeway_hit": _tw["hit"] if _tw else 0.0,
        "threeway_pick": _tw["pick"] if _tw else _AOD,
        "gn_hit": _gn["hit"] if _gn else 0.0,
        "cn_hit": _cn["hit"] if _cn else 0.0,
        "n_fixtures": _tw["n"] if _tw else (_gn["n"] if _gn else 0),
        "composite": _composite(_cell),
        "promote_status": "PROVISIONAL" if _cell.get("provisional") else "PASS",
        "provisional": bool(_cell.get("provisional")),
    }
