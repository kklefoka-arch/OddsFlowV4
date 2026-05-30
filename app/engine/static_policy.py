"""OddsFlow v4 Policy — 2-key (zone, bts) where bts ∈ {over, under}
=================================================================
v4 (2026-05-30). The BTS axis is reduced to its PURE direction (over/under) — 8
cells, all n≥802, zero thin cells. The BTS strong/slight **spread**, **DF**, and
the **H2H-corner** count are SIGNALS, not cell axes (fresh test + feasibility
workflow: GO_WITH_CONDITIONS). Drawn in the analysis project:
``C:\\OddsFlow V4 Website\\policy\\v4_policy_candidate.txt``; evidence
``...\\test\\sheets\\v4_test_2026-05-30.xlsx``.

Markets per cell (unchanged from the running build):
  goals_nl   Over 1.5 (all zones)
  corners_nl Over 7.5 (strong) / Over 8.5 (rest)
  threeway   alpha-or-draw (favourite wins OR draw = WIN; no void)

Signals (per cell, under ``signals`` — NOT markets, the emit loop skips them):
  spread        : "display", or {goals_override_on:"strong", goals_hit, n}
  df            : "display", or {threeway_tilt_on:"DF2", df2_hit}
  h2h_corner    : "display"
No hard suppression gates. Hit-rate only — no Wilson, no EV.

Names V3_MARKETS / V3_ACTIVE / PROMOTED_CELLS kept for route compatibility.
"""
from __future__ import annotations

from typing import Any

LOW_ZONE_SUPPRESS: bool = False

_GL15 = "goals_over_15_odd"
_CL75 = "corners_over_75_odd"
_CL85 = "corners_over_85_odd"
_AOD = "alpha_or_draw"


# ---------------------------------------------------------------------------
# V3_MARKETS — 2-key (zone, bts). Market entries: goals_nl | corners_nl | threeway.
# Non-market keys (composite, signals) are skipped by the emit loop.
# ---------------------------------------------------------------------------
V3_MARKETS: dict[tuple[str, str], dict[str, Any]] = {

    ("strong", "over"): {
        "goals_nl":   {"line": 1.5, "hit": 71.7, "n": 2941, "odd_col": _GL15},
        "corners_nl": {"line": 7.5, "hit": 69.8, "n": 2281, "odd_col": _CL75},
        "threeway":   {"line": None, "pick": _AOD, "hit": 69.4, "n": 2941, "odd_col": None},
        "composite": 70.3,
        "signals": {"spread": "display", "df": "display", "h2h_corner": "display"},
    },
    ("strong", "under"): {
        "goals_nl":   {"line": 1.5, "hit": 66.7, "n": 4815, "odd_col": _GL15},
        "corners_nl": {"line": 7.5, "hit": 67.6, "n": 3259, "odd_col": _CL75},
        "threeway":   {"line": None, "pick": _AOD, "hit": 74.3, "n": 4815, "odd_col": None},
        "composite": 69.5,
        "signals": {"spread": "display",
                    "df": {"threeway_tilt_on": "DF2", "df2_hit": 79.8},
                    "h2h_corner": "display"},
    },
    ("standard", "over"): {
        "goals_nl":   {"line": 1.5, "hit": 77.3, "n": 10996, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 64.0, "n": 8382, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 72.7, "n": 10996, "odd_col": None},
        "composite": 71.3,
        "signals": {"spread": {"goals_override_on": "strong", "goals_hit": 83.8, "n": 876},
                    "df": {"threeway_tilt_on": "DF2", "df2_hit": 78.2},
                    "h2h_corner": "display"},
    },
    ("standard", "under"): {
        "goals_nl":   {"line": 1.5, "hit": 71.8, "n": 2062, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 56.5, "n": 1412, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 81.5, "n": 2062, "odd_col": None},
        "composite": 69.9,
        "signals": {"spread": "display", "df": "display", "h2h_corner": "display"},
    },
    ("low", "over"): {
        "goals_nl":   {"line": 1.5, "hit": 80.8, "n": 3147, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 66.2, "n": 2740, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 79.9, "n": 3147, "odd_col": None},
        "composite": 75.6,
        "signals": {"spread": {"goals_override_on": "strong", "goals_hit": 85.0, "n": 642},
                    "df": "display", "h2h_corner": "display"},
    },
    ("low", "under"): {
        "goals_nl":   {"line": 1.5, "hit": 71.1, "n": 802, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 55.8, "n": 565, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 88.4, "n": 802, "odd_col": None},
        "composite": 71.8,
        "signals": {"spread": "display", "df": "display", "h2h_corner": "display"},
    },
    ("one_sided", "over"): {
        "goals_nl":   {"line": 1.5, "hit": 84.4, "n": 2435, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 68.8, "n": 2279, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 88.1, "n": 2435, "odd_col": None},
        "composite": 80.4,
        "signals": {"spread": "display", "df": "display", "h2h_corner": "display"},
    },
    ("one_sided", "under"): {
        "goals_nl":   {"line": 1.5, "hit": 82.3, "n": 1373, "odd_col": _GL15},
        "corners_nl": {"line": 8.5, "hit": 65.1, "n": 1175, "odd_col": _CL85},
        "threeway":   {"line": None, "pick": _AOD, "hit": 94.3, "n": 1373, "odd_col": None},
        "composite": 80.6,
        "signals": {"spread": "display", "df": "display", "h2h_corner": "display"},
    },
}

V3_ACTIVE: dict[tuple[str, str], dict[str, Any]] = {
    k: v for k, v in V3_MARKETS.items()
    if not (LOW_ZONE_SUPPRESS and k[0] == "low")
}

# Market keys (everything else in a cell dict — composite, signals — is metadata).
MARKET_KEYS = ("goals_nl", "corners_nl", "threeway")


# ---------------------------------------------------------------------------
# PROMOTED_CELLS — display + inspector metadata (2-key). bts_pocket holds the
# over/under value (v4 cell axis) for back-compat with route field names.
# ---------------------------------------------------------------------------
PROMOTED_CELLS: dict[tuple[str, str], dict[str, Any]] = {}
for (_z, _b), _cell in V3_ACTIVE.items():
    _gn, _cn, _tw = _cell["goals_nl"], _cell["corners_nl"], _cell["threeway"]
    PROMOTED_CELLS[(_z, _b)] = {
        "zone": _z, "bts_pocket": _b,
        "cell_promoted": True,
        "threeway_hit": _tw["hit"], "threeway_pick": _tw["pick"],
        "gn_hit": _gn["hit"], "cn_hit": _cn["hit"],
        "n_fixtures": _tw["n"],
        "composite": _cell["composite"],
        "promote_status": "PASS",
        "provisional": False,
    }
