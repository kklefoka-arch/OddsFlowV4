"""OddsFlow V3 — Golden-Rule Zone-Market Policy
===============================================
Session 11 baseline (9 cells, 2-key) restored Session 19 (2026-05-28).
Boundaries re-cut per raw-notes overlay: excluded < 2.90, strong 2.90-3.30,
standard 3.30-3.80, low 3.80-4.30, one_sided >= 4.30. The prior V3 cutoffs
(2.70/3.40/4.10/4.80) let one_sided fixtures bleed into low — contaminating
low-zone hit rates around 50% and bleeding into standard.

Golden Rule (Notes 28-05-26): two emits per qualifying fixture.
  strong + standard slight BTS  -> DNB + line (goals or corners)
  low + one_sided slight BTS    -> alpha-win-or-draw / alpha-win + line

V3_MARKETS encodes that rule:
  strong cells     -> goals_nl + dnb         (2 emits)
  standard cells   -> goals_nl + corners_nl + dnb  (3 emits — operator picks
                       the line at the 3-picks-log layer based on edge)
  low cells        -> dnb + goals_nl O2.5    (2 emits)
  one_sided cells  -> alpha_win + goals_nl O2.5    (2 emits)

Baselines computed from the post-overlay DB at restore time (Session 19,
~46.9k settled fixtures). The 6-week settlement watch is what makes them
real-time accurate; the numbers below are reference / drift baseline.

PROMOTED_CELLS — fallback dict consumed by routes_inspector / routes_reports.
V3_MARKETS     — per-cell pick configuration consumed by routes_picks.
V3_ACTIVE      — V3_MARKETS filtered by LOW_ZONE_SUPPRESS (low active here).
"""

from __future__ import annotations

from typing import Any

LOW_ZONE_SUPPRESS: bool = False   # V3 activates low zone (DNB + goals O2.5)

_DNB = "DNB (Alpha Win or Draw)"
_WIN = "Alpha Win"

# ---------------------------------------------------------------------------
# PROMOTED_CELLS — display + inspector metadata.
# Required fields: threeway_hit, n_fixtures, threeway_pick, cell_promoted,
#   zone, bts_pocket, gn_hit, cn_hit, promote_status.
# Hit rates are post-overlay baselines (Session 19) — see header.
# threeway_hit stores the DNB (strong/standard/low) or alpha_win (one_sided)
# baseline for the cell. gn_hit is the natural-line goals hit (O1.5 for
# strong/standard, O2.5 for low/one_sided). cn_hit is corners O8.5 in
# standard cells, 0 elsewhere (line not fired).
# ---------------------------------------------------------------------------
PROMOTED_CELLS: dict[tuple[str, str], dict[str, Any]] = {
    # -- strong zone -------------------------------------------------------
    ("strong", "slight_over"): {
        "zone": "strong", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 69.3, "threeway_pick": _DNB,
        "gn_hit": 71.6, "cn_hit": 0.0, "n_fixtures": 2929,
        "promote_status": "PASS",
    },
    ("strong", "slight_under"): {
        "zone": "strong", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 74.2, "threeway_pick": _DNB,
        "gn_hit": 66.8, "cn_hit": 0.0, "n_fixtures": 4795,
        "promote_status": "PASS",
    },
    # -- standard zone -----------------------------------------------------
    ("standard", "slight_over"): {
        "zone": "standard", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 73.1, "threeway_pick": _DNB,
        "gn_hit": 76.7, "cn_hit": 63.6, "n_fixtures": 10098,
        "promote_status": "PASS",
    },
    ("standard", "strong_over"): {
        "zone": "standard", "bts_pocket": "strong_over",
        "cell_promoted": True,
        "threeway_hit": 67.4, "threeway_pick": _DNB,
        "gn_hit": 83.8, "cn_hit": 68.3, "n_fixtures": 873,
        "promote_status": "PASS",
    },
    ("standard", "slight_under"): {
        "zone": "standard", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 81.5, "threeway_pick": _DNB,
        "gn_hit": 71.8, "cn_hit": 56.7, "n_fixtures": 2040,
        "promote_status": "MARGINAL",
    },
    # -- low zone (Golden Rule: dnb + goals O2.5) --------------------------
    ("low", "slight_over"): {
        "zone": "low", "bts_pocket": "slight_over",
        "cell_promoted": not LOW_ZONE_SUPPRESS,
        "threeway_hit": 81.4, "threeway_pick": _DNB,
        "gn_hit": 56.0, "cn_hit": 0.0, "n_fixtures": 2501,
        "promote_status": "PASS",
    },
    ("low", "slight_under"): {
        "zone": "low", "bts_pocket": "slight_under",
        "cell_promoted": not LOW_ZONE_SUPPRESS,
        "threeway_hit": 88.6, "threeway_pick": _DNB,
        "gn_hit": 48.5, "cn_hit": 0.0, "n_fixtures": 783,
        "promote_status": "PASS",
    },
    ("low", "strong_over"): {
        "zone": "low", "bts_pocket": "strong_over",
        "cell_promoted": not LOW_ZONE_SUPPRESS,
        "threeway_hit": 74.0, "threeway_pick": _DNB,
        "gn_hit": 67.1, "cn_hit": 0.0, "n_fixtures": 639,
        "promote_status": "PASS",
    },
    # NOTE: ("low", "strong_under") deferred — n=18 too small to be meaningful.
    #       Re-evaluate after 6-week post-overlay settlement when sample grows.
    # -- one_sided zone (Golden Rule: alpha_win + goals O2.5) --------------
    ("one_sided", "slight_over"): {
        "zone": "one_sided", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 72.5, "threeway_pick": _WIN,
        "gn_hit": 65.9, "cn_hit": 0.0, "n_fixtures": 2215,
        "promote_status": "PASS",
    },
    ("one_sided", "slight_under"): {
        "zone": "one_sided", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 77.1, "threeway_pick": _WIN,
        "gn_hit": 61.1, "cn_hit": 0.0, "n_fixtures": 1307,
        "promote_status": "PASS",
    },
    ("one_sided", "strong_over"): {
        "zone": "one_sided", "bts_pocket": "strong_over",
        "cell_promoted": True,
        "threeway_hit": 60.5, "threeway_pick": _WIN,
        "gn_hit": 67.6, "cn_hit": 0.0, "n_fixtures": 210,
        "promote_status": "FLAG",
    },
    ("one_sided", "strong_under"): {
        "zone": "one_sided", "bts_pocket": "strong_under",
        "cell_promoted": True,
        "threeway_hit": 75.4, "threeway_pick": _WIN,
        "gn_hit": 49.2, "cn_hit": 0.0, "n_fixtures": 65,
        "promote_status": "PASS",
    },
}

# ---------------------------------------------------------------------------
# V3_MARKETS — per-cell pick configuration (Golden Rule layout).
# market keys: "goals_nl" | "corners_nl" | "dnb" | "alpha_win"
# Fields: line (float | None), hit (float), n (int), odd_col (str | None)
#
# Natural goals line per zone:
#   strong / standard -> 1.5 (goals_over_15_odd)
#   low / one_sided   -> 2.5 (goals_over_25_odd)
# Natural corners line per zone:
#   standard -> 8.5 (corners_over_85_odd)  [fired only here in V3]
# ---------------------------------------------------------------------------
_GL15 = "goals_over_15_odd"
_GL25 = "goals_over_25_odd"
_CL85 = "corners_over_85_odd"

V3_MARKETS: dict[tuple[str, str], dict[str, dict[str, Any]]] = {
    # -- strong (2 emits per cell — Golden Rule) ---------------------------
    ("strong", "slight_over"): {
        "goals_nl": {"line": 1.5,  "hit": 71.6, "n": 2929, "odd_col": _GL15},
        "dnb":      {"line": None, "hit": 69.3, "n": 2929, "odd_col": None},
    },
    ("strong", "slight_under"): {
        "goals_nl": {"line": 1.5,  "hit": 66.8, "n": 4795, "odd_col": _GL15},
        "dnb":      {"line": None, "hit": 74.2, "n": 4795, "odd_col": None},
    },
    # -- standard (3 emits per cell — Golden Rule) -------------------------
    ("standard", "slight_over"): {
        "goals_nl":   {"line": 1.5,  "hit": 76.7, "n": 10098, "odd_col": _GL15},
        "corners_nl": {"line": 8.5,  "hit": 63.6, "n":  7612, "odd_col": _CL85},
        "dnb":        {"line": None, "hit": 73.1, "n": 10098, "odd_col": None},
    },
    ("standard", "strong_over"): {
        "goals_nl":   {"line": 1.5,  "hit": 83.8, "n":  873, "odd_col": _GL15},
        "corners_nl": {"line": 8.5,  "hit": 68.3, "n":  756, "odd_col": _CL85},
        "dnb":        {"line": None, "hit": 67.4, "n":  873, "odd_col": None},
    },
    ("standard", "slight_under"): {
        "goals_nl":   {"line": 1.5,  "hit": 71.8, "n": 2040, "odd_col": _GL15},
        "corners_nl": {"line": 8.5,  "hit": 56.7, "n": 1402, "odd_col": _CL85},
        "dnb":        {"line": None, "hit": 81.5, "n": 2040, "odd_col": None},
    },
    # -- low (2 emits per cell — Golden Rule) ------------------------------
    ("low", "slight_over"): {
        "dnb":      {"line": None, "hit": 81.4, "n": 2501, "odd_col": None},
        "goals_nl": {"line": 2.5,  "hit": 56.0, "n": 2501, "odd_col": _GL25},
    },
    ("low", "slight_under"): {
        "dnb":      {"line": None, "hit": 88.6, "n":  783, "odd_col": None},
        "goals_nl": {"line": 2.5,  "hit": 48.5, "n":  783, "odd_col": _GL25},
    },
    ("low", "strong_over"): {
        "dnb":      {"line": None, "hit": 74.0, "n":  639, "odd_col": None},
        "goals_nl": {"line": 2.5,  "hit": 67.1, "n":  639, "odd_col": _GL25},
    },
    # ("low", "strong_under") deferred — n=18 too small (see PROMOTED_CELLS note).
    # -- one_sided (2 emits per cell — Golden Rule) ------------------------
    ("one_sided", "slight_over"): {
        "alpha_win": {"line": None, "hit": 72.5, "n": 2215, "odd_col": None},
        "goals_nl":  {"line": 2.5,  "hit": 65.9, "n": 2215, "odd_col": _GL25},
    },
    ("one_sided", "slight_under"): {
        "alpha_win": {"line": None, "hit": 77.1, "n": 1307, "odd_col": None},
        "goals_nl":  {"line": 2.5,  "hit": 61.1, "n": 1307, "odd_col": _GL25},
    },
    ("one_sided", "strong_over"): {
        "alpha_win": {"line": None, "hit": 60.5, "n":  210, "odd_col": None},
        "goals_nl":  {"line": 2.5,  "hit": 67.6, "n":  210, "odd_col": _GL25},
    },
    ("one_sided", "strong_under"): {
        "alpha_win": {"line": None, "hit": 75.4, "n":   65, "odd_col": None},
        "goals_nl":  {"line": 2.5,  "hit": 49.2, "n":   65, "odd_col": _GL25},
    },
}

# Active pick set — low zone excluded when LOW_ZONE_SUPPRESS is True.
V3_ACTIVE: dict[tuple[str, str], dict[str, dict[str, Any]]] = {
    k: v for k, v in V3_MARKETS.items()
    if not (LOW_ZONE_SUPPRESS and k[0] == "low")
}
