"""
Hardcoded V3 Foundation Matrix policy — stone baseline from 28,425-fixture analysis.

These values never drift with local DB state. compute_foundation() still runs
for the /foundation view page; picks use this module exclusively.

Source: V3 Foundation Matrix analysis (settled fixtures, V3 rules).
3-Way baseline avg across promoted cells: 74.6%.
Goals peak 64.1% (standard×strong_over), corners peak 58.9% — neither qualifies.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Promoted cell table
# Fields required by picks.html: gn_hit, cn_hit, threeway_hit,
#   n_fixtures, threeway_pick, cell_promoted, zone, bts_pocket.
# ---------------------------------------------------------------------------

_DNB = "DNB (Alpha Win or Draw)"
_WIN = "Alpha Win"

PROMOTED_CELLS: dict[tuple[str, str], dict[str, Any]] = {
    # ── strong zone (draw_odd 2.70–3.40) ─────────────────────────────────
    ("strong", "slight_over"): {
        "zone": "strong", "bts_pocket": "slight_over",
        "cell_promoted": True, "markets": ("dnb",),
        "threeway_hit": 70.5, "threeway_pick": _DNB,
        "gn_hit": 61.2, "cn_hit": 56.4, "n_fixtures": 4997,
        "promote_status": "PROMOTE_TOLERANCE",
    },
    ("strong", "slight_under"): {
        "zone": "strong", "bts_pocket": "slight_under",
        "cell_promoted": True, "markets": ("dnb",),
        "threeway_hit": 74.9, "threeway_pick": _DNB,
        "gn_hit": 60.8, "cn_hit": 55.9, "n_fixtures": 5925,
        "promote_status": "PROMOTE",
    },
    ("strong", "strong_under"): {
        "zone": "strong", "bts_pocket": "strong_under",
        "cell_promoted": True, "markets": ("dnb",),
        "threeway_hit": 87.9, "threeway_pick": _DNB,
        "gn_hit": 59.1, "cn_hit": 54.2, "n_fixtures": 33,
        "promote_status": "PROMOTE",
    },
    # ── standard zone (draw_odd 3.40–4.10) ───────────────────────────────
    ("standard", "slight_over"): {
        "zone": "standard", "bts_pocket": "slight_over",
        "cell_promoted": True, "markets": ("dnb",),
        "threeway_hit": 74.8, "threeway_pick": _DNB,
        "gn_hit": 63.5, "cn_hit": 57.8, "n_fixtures": 9449,
        "promote_status": "PROMOTE",
    },
    ("standard", "strong_over"): {
        "zone": "standard", "bts_pocket": "strong_over",
        "cell_promoted": True, "markets": ("dnb",),
        "threeway_hit": 69.4, "threeway_pick": _DNB,
        "gn_hit": 64.1, "cn_hit": 58.9, "n_fixtures": 1319,
        "promote_status": "PROMOTE_TOLERANCE",
    },
    ("standard", "slight_under"): {
        "zone": "standard", "bts_pocket": "slight_under",
        "cell_promoted": True, "markets": ("dnb",),
        "threeway_hit": 82.8, "threeway_pick": _DNB,
        "gn_hit": 62.7, "cn_hit": 56.1, "n_fixtures": 1940,
        "promote_status": "PROMOTE",
    },
    ("standard", "strong_under"): {
        "zone": "standard", "bts_pocket": "strong_under",
        "cell_promoted": True, "markets": ("dnb",),
        "threeway_hit": 84.6, "threeway_pick": _DNB,
        "gn_hit": 61.0, "cn_hit": 55.3, "n_fixtures": 26,
        "promote_status": "PROMOTE",
    },
    # ── one_sided zone (draw_odd 4.80+) ──────────────────────────────────
    ("one_sided", "slight_over"): {
        "zone": "one_sided", "bts_pocket": "slight_over",
        "cell_promoted": True, "markets": ("alpha_win",),
        "threeway_hit": 76.6, "threeway_pick": _WIN,
        "gn_hit": 58.3, "cn_hit": 52.1, "n_fixtures": 1119,
        "promote_status": "PROMOTE",
    },
    ("one_sided", "slight_under"): {
        "zone": "one_sided", "bts_pocket": "slight_under",
        "cell_promoted": True, "markets": ("alpha_win",),
        "threeway_hit": 81.0, "threeway_pick": _WIN,
        "gn_hit": 57.6, "cn_hit": 51.8, "n_fixtures": 814,
        "promote_status": "PROMOTE",
    },
    ("one_sided", "strong_under"): {
        "zone": "one_sided", "bts_pocket": "strong_under",
        "cell_promoted": True, "markets": ("alpha_win",),
        "threeway_hit": 80.9, "threeway_pick": _WIN,
        "gn_hit": 56.9, "cn_hit": 50.4, "n_fixtures": 47,
        "promote_status": "PROMOTE",
    },
}
