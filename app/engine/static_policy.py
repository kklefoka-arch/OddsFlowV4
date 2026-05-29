"""OddsFlow V3.2 — DF-aware Golden-Rule Zone-Market Policy
==========================================================
Session 23c (2026-05-29) — Durable Rule 1 overridden by operator decision.

Partition is now 3-key ``(zone, DF, bts_pocket)``. DF re-introduced as an
analytical axis after the Session 17 enhanced analysis showed 20-30pp
separation per zone on alpha_win and 12.8pp on strong:slight_under dnb.
Re-computed under the Session-19 raw-notes boundary overlay using the live
``oddsflow_v4.db`` (28,508 settled fixtures, min_n=45, min_corners_n=30).

What V3.2 keeps from V3 (Session 19):
  - Raw-notes zone boundaries: excluded < 2.90, strong 2.90-3.30,
    standard 3.30-3.80, low 3.80-4.30, one_sided >= 4.30.
  - Golden Rule per-cell market set (Notes 28-05-26):
        strong    -> goals_nl O1.5 + dnb
        standard  -> goals_nl O1.5 + corners_nl O8.5 + dnb
        low       -> dnb + goals_nl O2.5
        one_sided -> alpha_win + goals_nl O2.5
  - V3 non-loss hit-rate convention (voids count as wins for DNB).

What V3.2 adds back from V3.1 (with operator override of Rule 1):
  - DF axis: DF0 / DF1 / DF2 (3-bucket).
  - 20-cell partition (was 12 in Session 19++).

What V3.2 explicitly does NOT include (Durable Rules 2-4 still hold):
  - No Wilson lower bound anywhere — promotion is empirical hit-rate only.
  - No EV / breakeven / economic models anywhere.
  - No PR-X9 ranker overlay (retired Session 19).

PROMOTED_CELLS — display + inspector metadata, 3-key.
V3_MARKETS     — per-cell pick configuration consumed by routes_picks.
V3_ACTIVE      — V3_MARKETS (LOW_ZONE_SUPPRESS retained as a flag for
                 backward compatibility but defaults to False; low zone fires).
"""

from __future__ import annotations

from typing import Any

LOW_ZONE_SUPPRESS: bool = False   # V3.2 keeps low zone active.

_DNB = "DNB (Alpha Win or Draw)"
_WIN = "Alpha Win"


# ---------------------------------------------------------------------------
# PROMOTED_CELLS — display + inspector metadata (3-key).
# Required fields: zone, df, bts_pocket, threeway_hit, threeway_pick,
#   gn_hit, cn_hit, n_fixtures, cell_promoted, promote_status.
# Promote_status is empirical only: PASS when min_n is met and the primary
# market hit clears a reasonable empirical floor (no Wilson, no EV).
# ---------------------------------------------------------------------------
PROMOTED_CELLS: dict[tuple[str, str, str], dict[str, Any]] = {
    # -- strong zone -------------------------------------------------------
    ("strong", "DF0", "slight_over"): {
        "zone": "strong", "df": "DF0", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 64.5, "threeway_pick": _DNB,
        "gn_hit": 70.2, "cn_hit": 0.0, "n_fixtures": 527,
        "promote_status": "PASS",
    },
    ("strong", "DF0", "slight_under"): {
        "zone": "strong", "df": "DF0", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 66.9, "threeway_pick": _DNB,
        "gn_hit": 66.6, "cn_hit": 0.0, "n_fixtures": 602,
        "promote_status": "PASS",
    },
    ("strong", "DF1", "slight_over"): {
        "zone": "strong", "df": "DF1", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 70.0, "threeway_pick": _DNB,
        "gn_hit": 72.2, "cn_hit": 0.0, "n_fixtures": 2189,
        "promote_status": "PASS",
    },
    ("strong", "DF1", "slight_under"): {
        "zone": "strong", "df": "DF1", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 71.4, "threeway_pick": _DNB,
        "gn_hit": 67.2, "cn_hit": 0.0, "n_fixtures": 2233,
        "promote_status": "PASS",
    },
    ("strong", "DF2", "slight_over"): {
        "zone": "strong", "df": "DF2", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 74.2, "threeway_pick": _DNB,
        "gn_hit": 69.5, "cn_hit": 0.0, "n_fixtures": 213,
        "promote_status": "PASS",
    },
    ("strong", "DF2", "slight_under"): {
        "zone": "strong", "df": "DF2", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 79.7, "threeway_pick": _DNB,
        "gn_hit": 66.4, "cn_hit": 0.0, "n_fixtures": 1960,
        "promote_status": "PASS",
    },
    # -- standard zone -----------------------------------------------------
    ("standard", "DF0", "slight_over"): {
        "zone": "standard", "df": "DF0", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 65.7, "threeway_pick": _DNB,
        "gn_hit": 76.3, "cn_hit": 61.5, "n_fixtures": 388,
        "promote_status": "PASS",
    },
    ("standard", "DF0", "strong_over"): {
        "zone": "standard", "df": "DF0", "bts_pocket": "strong_over",
        "cell_promoted": True,
        "threeway_hit": 61.8, "threeway_pick": _DNB,
        "gn_hit": 78.9, "cn_hit": 59.4, "n_fixtures": 76,
        "promote_status": "PASS",
    },
    ("standard", "DF1", "slight_over"): {
        "zone": "standard", "df": "DF1", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 70.2, "threeway_pick": _DNB,
        "gn_hit": 77.8, "cn_hit": 64.1, "n_fixtures": 5811,
        "promote_status": "PASS",
    },
    ("standard", "DF1", "strong_over"): {
        "zone": "standard", "df": "DF1", "bts_pocket": "strong_over",
        "cell_promoted": True,
        "threeway_hit": 67.4, "threeway_pick": _DNB,
        "gn_hit": 84.4, "cn_hit": 68.6, "n_fixtures": 770,
        "promote_status": "PASS",
    },
    ("standard", "DF2", "slight_over"): {
        "zone": "standard", "df": "DF2", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 78.1, "threeway_pick": _DNB,
        "gn_hit": 75.2, "cn_hit": 63.1, "n_fixtures": 3899,
        "promote_status": "PASS",
    },
    ("standard", "DF2", "slight_under"): {
        "zone": "standard", "df": "DF2", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 81.6, "threeway_pick": _DNB,
        "gn_hit": 71.8, "cn_hit": 57.1, "n_fixtures": 2017,
        "promote_status": "PASS",
    },
    # -- low zone (Golden Rule: dnb + goals O2.5) --------------------------
    ("low", "DF1", "strong_over"): {
        "zone": "low", "df": "DF1", "bts_pocket": "strong_over",
        "cell_promoted": True,
        "threeway_hit": 71.4, "threeway_pick": _DNB,
        "gn_hit": 68.4, "cn_hit": 0.0, "n_fixtures": 329,
        "promote_status": "PASS",
    },
    ("low", "DF2", "slight_over"): {
        "zone": "low", "df": "DF2", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 81.7, "threeway_pick": _DNB,
        "gn_hit": 55.9, "cn_hit": 0.0, "n_fixtures": 2469,
        "promote_status": "PASS",
    },
    ("low", "DF2", "slight_under"): {
        "zone": "low", "df": "DF2", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 88.6, "threeway_pick": _DNB,
        "gn_hit": 48.5, "cn_hit": 0.0, "n_fixtures": 783,
        "promote_status": "PASS",
    },
    ("low", "DF2", "strong_over"): {
        "zone": "low", "df": "DF2", "bts_pocket": "strong_over",
        "cell_promoted": True,
        "threeway_hit": 78.2, "threeway_pick": _DNB,
        "gn_hit": 64.7, "cn_hit": 0.0, "n_fixtures": 289,
        "promote_status": "PASS",
    },
    # -- one_sided zone (Golden Rule: alpha_win + goals O2.5) --------------
    ("one_sided", "DF2", "slight_over"): {
        "zone": "one_sided", "df": "DF2", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 72.5, "threeway_pick": _WIN,
        "gn_hit": 65.8, "cn_hit": 0.0, "n_fixtures": 2213,
        "promote_status": "PASS",
    },
    ("one_sided", "DF2", "slight_under"): {
        "zone": "one_sided", "df": "DF2", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 77.1, "threeway_pick": _WIN,
        "gn_hit": 61.1, "cn_hit": 0.0, "n_fixtures": 1307,
        "promote_status": "PASS",
    },
    ("one_sided", "DF2", "strong_over"): {
        "zone": "one_sided", "df": "DF2", "bts_pocket": "strong_over",
        "cell_promoted": True,
        "threeway_hit": 61.0, "threeway_pick": _WIN,
        "gn_hit": 68.3, "cn_hit": 0.0, "n_fixtures": 205,
        "promote_status": "PASS",
    },
    ("one_sided", "DF2", "strong_under"): {
        "zone": "one_sided", "df": "DF2", "bts_pocket": "strong_under",
        "cell_promoted": True,
        "threeway_hit": 75.4, "threeway_pick": _WIN,
        "gn_hit": 49.2, "cn_hit": 0.0, "n_fixtures": 65,
        "promote_status": "PASS",
    },
}


# ---------------------------------------------------------------------------
# V3_MARKETS — per-cell pick configuration (3-key, Golden Rule layout).
# market keys: "goals_nl" | "corners_nl" | "dnb" | "alpha_win"
# Fields: line (float | None), hit (float), n (int), odd_col (str | None)
#
# Goals natural line per zone:
#   strong / standard -> 1.5  (goals_over_15_odd)
#   low / one_sided   -> 2.5  (goals_over_25_odd)
# Corners natural line:
#   standard -> 8.5  (corners_over_85_odd, fired only here in V3)
# ---------------------------------------------------------------------------
_GL15 = "goals_over_15_odd"
_GL25 = "goals_over_25_odd"
_CL85 = "corners_over_85_odd"

V3_MARKETS: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = {
    # -- strong -------------------------------------------------------------
    ("strong", "DF0", "slight_over"): {
        "goals_nl": {"line": 1.5,  "hit": 70.2, "n": 527,  "odd_col": _GL15},
        "dnb":      {"line": None, "hit": 64.5, "n": 527,  "odd_col": None},
    },
    ("strong", "DF0", "slight_under"): {
        "goals_nl": {"line": 1.5,  "hit": 66.6, "n": 602,  "odd_col": _GL15},
        "dnb":      {"line": None, "hit": 66.9, "n": 602,  "odd_col": None},
    },
    ("strong", "DF1", "slight_over"): {
        "goals_nl": {"line": 1.5,  "hit": 72.2, "n": 2189, "odd_col": _GL15},
        "dnb":      {"line": None, "hit": 70.0, "n": 2189, "odd_col": None},
    },
    ("strong", "DF1", "slight_under"): {
        "goals_nl": {"line": 1.5,  "hit": 67.2, "n": 2233, "odd_col": _GL15},
        "dnb":      {"line": None, "hit": 71.4, "n": 2233, "odd_col": None},
    },
    ("strong", "DF2", "slight_over"): {
        "goals_nl": {"line": 1.5,  "hit": 69.5, "n": 213,  "odd_col": _GL15},
        "dnb":      {"line": None, "hit": 74.2, "n": 213,  "odd_col": None},
    },
    ("strong", "DF2", "slight_under"): {
        "goals_nl": {"line": 1.5,  "hit": 66.4, "n": 1960, "odd_col": _GL15},
        "dnb":      {"line": None, "hit": 79.7, "n": 1960, "odd_col": None},
    },
    # -- standard -----------------------------------------------------------
    ("standard", "DF0", "slight_over"): {
        "goals_nl":   {"line": 1.5,  "hit": 76.3, "n": 388, "odd_col": _GL15},
        "corners_nl": {"line": 8.5,  "hit": 61.5, "n": 314, "odd_col": _CL85},
        "dnb":        {"line": None, "hit": 65.7, "n": 388, "odd_col": None},
    },
    ("standard", "DF0", "strong_over"): {
        "goals_nl":   {"line": 1.5,  "hit": 78.9, "n":  76, "odd_col": _GL15},
        "corners_nl": {"line": 8.5,  "hit": 59.4, "n":  64, "odd_col": _CL85},
        "dnb":        {"line": None, "hit": 61.8, "n":  76, "odd_col": None},
    },
    ("standard", "DF1", "slight_over"): {
        "goals_nl":   {"line": 1.5,  "hit": 77.8, "n": 5811, "odd_col": _GL15},
        "corners_nl": {"line": 8.5,  "hit": 64.1, "n": 4277, "odd_col": _CL85},
        "dnb":        {"line": None, "hit": 70.2, "n": 5811, "odd_col": None},
    },
    ("standard", "DF1", "strong_over"): {
        "goals_nl":   {"line": 1.5,  "hit": 84.4, "n":  770, "odd_col": _GL15},
        "corners_nl": {"line": 8.5,  "hit": 68.6, "n":  668, "odd_col": _CL85},
        "dnb":        {"line": None, "hit": 67.4, "n":  770, "odd_col": None},
    },
    ("standard", "DF2", "slight_over"): {
        "goals_nl":   {"line": 1.5,  "hit": 75.2, "n": 3899, "odd_col": _GL15},
        "corners_nl": {"line": 8.5,  "hit": 63.1, "n": 3021, "odd_col": _CL85},
        "dnb":        {"line": None, "hit": 78.1, "n": 3899, "odd_col": None},
    },
    ("standard", "DF2", "slight_under"): {
        "goals_nl":   {"line": 1.5,  "hit": 71.8, "n": 2017, "odd_col": _GL15},
        "corners_nl": {"line": 8.5,  "hit": 57.1, "n": 1388, "odd_col": _CL85},
        "dnb":        {"line": None, "hit": 81.6, "n": 2017, "odd_col": None},
    },
    # -- low ----------------------------------------------------------------
    ("low", "DF1", "strong_over"): {
        "dnb":      {"line": None, "hit": 71.4, "n": 329, "odd_col": None},
        "goals_nl": {"line": 2.5,  "hit": 68.4, "n": 329, "odd_col": _GL25},
    },
    ("low", "DF2", "slight_over"): {
        "dnb":      {"line": None, "hit": 81.7, "n": 2469, "odd_col": None},
        "goals_nl": {"line": 2.5,  "hit": 55.9, "n": 2469, "odd_col": _GL25},
    },
    ("low", "DF2", "slight_under"): {
        "dnb":      {"line": None, "hit": 88.6, "n":  783, "odd_col": None},
        "goals_nl": {"line": 2.5,  "hit": 48.5, "n":  783, "odd_col": _GL25},
    },
    ("low", "DF2", "strong_over"): {
        "dnb":      {"line": None, "hit": 78.2, "n":  289, "odd_col": None},
        "goals_nl": {"line": 2.5,  "hit": 64.7, "n":  289, "odd_col": _GL25},
    },
    # -- one_sided ----------------------------------------------------------
    ("one_sided", "DF2", "slight_over"): {
        "alpha_win": {"line": None, "hit": 72.5, "n": 2213, "odd_col": None},
        "goals_nl":  {"line": 2.5,  "hit": 65.8, "n": 2213, "odd_col": _GL25},
    },
    ("one_sided", "DF2", "slight_under"): {
        "alpha_win": {"line": None, "hit": 77.1, "n": 1307, "odd_col": None},
        "goals_nl":  {"line": 2.5,  "hit": 61.1, "n": 1307, "odd_col": _GL25},
    },
    ("one_sided", "DF2", "strong_over"): {
        "alpha_win": {"line": None, "hit": 61.0, "n":  205, "odd_col": None},
        "goals_nl":  {"line": 2.5,  "hit": 68.3, "n":  205, "odd_col": _GL25},
    },
    ("one_sided", "DF2", "strong_under"): {
        "alpha_win": {"line": None, "hit": 75.4, "n":   65, "odd_col": None},
        "goals_nl":  {"line": 2.5,  "hit": 49.2, "n":   65, "odd_col": _GL25},
    },
}

# Active pick set — low zone kept active in V3.2 (LOW_ZONE_SUPPRESS=False).
V3_ACTIVE: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = {
    k: v for k, v in V3_MARKETS.items()
    if not (LOW_ZONE_SUPPRESS and k[0] == "low")
}
