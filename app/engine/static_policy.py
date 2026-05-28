"""OddsFlow V3 — Validated Zone-Market Policy
============================================
Stone baseline from 28,473-fixture analysis (Phase 8, 2026-05-25).
Results: 10 PASS / 1 MARGINAL / 1 FLAG.

PROMOTED_CELLS — compatible fallback dict (inspector / reports routes).
V3_MARKETS     — per-cell market configuration.
V3_ACTIVE      — active pick set (low zone governed by LOW_ZONE_SUPPRESS).
"""

from __future__ import annotations

from typing import Any

LOW_ZONE_SUPPRESS: bool = False   # V3 policy activates low zone DNB

_DNB = "DNB (Alpha Win or Draw)"
_WIN = "Alpha Win"

# ---------------------------------------------------------------------------
# PROMOTED_CELLS — fallback dict consumed by routes_inspector / routes_reports.
# Required fields: threeway_hit, n_fixtures, threeway_pick, cell_promoted,
#   zone, bts_pocket, gn_hit, cn_hit, promote_status.
# threeway_hit is kept for inspector compat; for strong/standard it stores the
# historical DNB baseline (not the V3 pick market).
# ---------------------------------------------------------------------------
PROMOTED_CELLS: dict[tuple[str, str], dict[str, Any]] = {
    # ── strong zone ──────────────────────────────────────────────────────
    ("strong", "slight_over"): {
        "zone": "strong", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 70.5, "threeway_pick": _DNB,
        "gn_hit": 72.2, "cn_hit": 64.5, "n_fixtures": 4997,
        "promote_status": "PASS",
    },
    ("strong", "slight_under"): {
        "zone": "strong", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 74.9, "threeway_pick": _DNB,
        "gn_hit": 66.6, "cn_hit": 55.9, "n_fixtures": 5925,
        "promote_status": "PASS",
    },
    # ── standard zone ────────────────────────────────────────────────────
    ("standard", "slight_over"): {
        "zone": "standard", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 74.8, "threeway_pick": _DNB,
        "gn_hit": 78.2, "cn_hit": 64.5, "n_fixtures": 9449,
        "promote_status": "PASS",
    },
    ("standard", "strong_over"): {
        "zone": "standard", "bts_pocket": "strong_over",
        "cell_promoted": True,
        "threeway_hit": 69.4, "threeway_pick": _DNB,
        "gn_hit": 83.7, "cn_hit": 69.9, "n_fixtures": 1319,
        "promote_status": "PASS",
    },
    ("standard", "slight_under"): {
        "zone": "standard", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 82.8, "threeway_pick": _DNB,
        "gn_hit": 71.6, "cn_hit": 57.8, "n_fixtures": 1940,
        "promote_status": "MARGINAL",
    },
    # ── low zone ─────────────────────────────────────────────────────────
    ("low", "slight_over"): {
        "zone": "low", "bts_pocket": "slight_over",
        "cell_promoted": not LOW_ZONE_SUPPRESS,
        "threeway_hit": 84.9, "threeway_pick": _DNB,
        "gn_hit": 0.0, "cn_hit": 0.0, "n_fixtures": 1733,
        "promote_status": "PASS",
    },
    ("low", "slight_under"): {
        "zone": "low", "bts_pocket": "slight_under",
        "cell_promoted": not LOW_ZONE_SUPPRESS,
        "threeway_hit": 91.6, "threeway_pick": _DNB,
        "gn_hit": 0.0, "cn_hit": 0.0, "n_fixtures": 675,
        "promote_status": "PASS",
    },
    # ── one_sided zone ───────────────────────────────────────────────────
    ("one_sided", "slight_over"): {
        "zone": "one_sided", "bts_pocket": "slight_over",
        "cell_promoted": True,
        "threeway_hit": 76.6, "threeway_pick": _WIN,
        "gn_hit": 58.3, "cn_hit": 52.1, "n_fixtures": 1119,
        "promote_status": "PASS",
    },
    ("one_sided", "slight_under"): {
        "zone": "one_sided", "bts_pocket": "slight_under",
        "cell_promoted": True,
        "threeway_hit": 81.0, "threeway_pick": _WIN,
        "gn_hit": 57.6, "cn_hit": 51.8, "n_fixtures": 814,
        "promote_status": "PASS",
    },
}

# ---------------------------------------------------------------------------
# V3_MARKETS — per-cell pick configuration.
# market keys: "goals_nl" | "corners_nl" | "dnb" | "alpha_win"
# Fields: line (float | None), hit (float), n (int), odd_col (str | None)
# ---------------------------------------------------------------------------
_GL = "goals_over_15_odd"
_CL = "corners_over_85_odd"

V3_MARKETS: dict[tuple[str, str], dict[str, dict[str, Any]]] = {
    # ── strong ───────────────────────────────────────────────────────────
    ("strong", "slight_over"):  {
        "goals_nl": {"line": 1.5, "hit": 72.2, "n": 4997, "odd_col": _GL},
    },
    ("strong", "slight_under"): {
        "goals_nl": {"line": 1.5, "hit": 66.6, "n": 5925, "odd_col": _GL},
    },
    # ── standard ─────────────────────────────────────────────────────────
    ("standard", "slight_over"): {
        "goals_nl":   {"line": 1.5, "hit": 78.2, "n": 9449, "odd_col": _GL},
        "corners_nl": {"line": 8.5, "hit": 64.5, "n": 7274, "odd_col": _CL},
    },
    ("standard", "strong_over"): {
        "goals_nl":   {"line": 1.5, "hit": 83.7, "n": 1319, "odd_col": _GL},
        "corners_nl": {"line": 8.5, "hit": 69.9, "n": 1173, "odd_col": _CL},
    },
    ("standard", "slight_under"): {
        "goals_nl":   {"line": 1.5, "hit": 71.6, "n": 1940, "odd_col": _GL},
        "corners_nl": {"line": 8.5, "hit": 57.8, "n": 1316, "odd_col": _CL},
    },
    # ── low ──────────────────────────────────────────────────────────────
    ("low", "slight_over"):  {"dnb": {"line": None, "hit": 84.9, "n": 1733, "odd_col": None}},
    ("low", "slight_under"): {"dnb": {"line": None, "hit": 91.6, "n":  675, "odd_col": None}},
    # ── one_sided ────────────────────────────────────────────────────────
    ("one_sided", "slight_over"):  {"alpha_win": {"line": None, "hit": 76.6, "n": 1119, "odd_col": None}},
    ("one_sided", "slight_under"): {"alpha_win": {"line": None, "hit": 81.0, "n":  814, "odd_col": None}},
}

# Active pick set — low zone excluded when LOW_ZONE_SUPPRESS is True
V3_ACTIVE: dict[tuple[str, str], dict[str, dict[str, Any]]] = {
    k: v for k, v in V3_MARKETS.items()
    if not (LOW_ZONE_SUPPRESS and k[0] == "low")
}
