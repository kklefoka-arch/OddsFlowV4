"""OddsFlow Ground-Zero — Foundation Matrix and Promotion Framework.

Computes per-(zone × bts_pocket) cell hit rates and applies promotion logic for
goals, corners, and 3-way markets across tier splits (all / T1+T2 / T3).

Re-Foundation (2026-05-30): 2-key ``(zone, bts_pocket)`` partition (DF is a
signal, not a cell axis); 3-way = alpha-or-draw in ALL zones; tier split is
T1+T2 vs T3.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.engine.classify import zone_of, bts_of
from app.engine.natural_lines import HALF_LINES, ZONES, BTS_POCKETS, natural_line, system_line

# ---------------------------------------------------------------------------
# Promotion constants
# ---------------------------------------------------------------------------
PROMOTE_THRESHOLD: float = 72.0      # % — hard promote
PROMOTE_LOWER: float = 67.5          # % — tolerance band lower bound
DROP_SECONDARY_GAP: float = 4.5      # pp — max extra drop vs rank-1 cell
LOW_ZONE_SUPPRESS: bool = False       # Session 23: aligned with static_policy.py (low zone fires live → display PROMOTE)

# Status string constants — exported for use in pick/route logic
PROMOTE: str = "PROMOTE"
PROMOTE_TOLERANCE: str = "PROMOTE_TOLERANCE"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hit_rate(numerator: int, denominator: int) -> float:
    """Safe percentage: 0.0 when denominator is zero."""
    return (numerator / denominator * 100.0) if denominator else 0.0


def _goals_green(row: dict, line: float) -> bool:
    """Total goals strictly greater than half-line."""
    total = row.get("total_goals")
    if total is None:
        hs = row.get("home_score")
        aws = row.get("away_score")
        if hs is None or aws is None:
            return False
        total = hs + aws
    return total > line


def _corners_green(row: dict, line: float) -> bool:
    """Total corners strictly greater than half-line."""
    total = row.get("total_corners")
    if total is None:
        hc = row.get("home_corners")
        ac = row.get("away_corners")
        if hc is None or ac is None:
            return False
        total = hc + ac
    return total > line


def _alpha_is_home(row: dict) -> bool:
    """Alpha (favourite) is the home team when home_odd ≤ away_odd."""
    h = row.get("home_odd")
    a = row.get("away_odd")
    if h is None or a is None:
        return True
    return h <= a


def _threeway_green(row: dict, zone: str) -> bool:
    """Evaluate 3-way pick green condition.

    Ground zero (all zones): alpha-or-draw = favourite wins OR draw. A draw is
    a protected WIN (no void). Straight-win lives in the advanced Optimistic config.
    """
    hs = row.get("home_score")
    aws = row.get("away_score")
    if hs is None or aws is None:
        return False

    alpha_home = _alpha_is_home(row)
    alpha_wins = (hs > aws) if alpha_home else (aws > hs)
    draw = (hs == aws)
    return alpha_wins or draw


def _promote_status(
    hit: float,
    drop: float,
    rank: int,
    rank1_drop: float,
    zone: str,
) -> str:
    """Apply promotion rules for goals/corners markets.

    Returns one of: PROMOTE, PROMOTE_TOLERANCE, HOLD, NO, MEASURING.
    """
    if hit >= PROMOTE_THRESHOLD:
        status = "PROMOTE"
    elif hit >= PROMOTE_LOWER:
        # tolerance band — check drop qualification
        drop_qualifies = rank == 1 or drop <= rank1_drop + DROP_SECONDARY_GAP
        status = "PROMOTE_TOLERANCE" if drop_qualifies else "HOLD"
    else:
        status = "NO"

    if LOW_ZONE_SUPPRESS and zone == "low" and status in ("PROMOTE", "PROMOTE_TOLERANCE"):
        return "MEASURING"
    return status


def _threeway_promote_status(hit: float, zone: str) -> str:
    """Apply promotion rules for 3-way market."""
    if hit >= PROMOTE_THRESHOLD:
        status = "PROMOTE"
    elif hit >= PROMOTE_LOWER:
        status = "PROMOTE_TOLERANCE"
    else:
        status = "NO"

    if LOW_ZONE_SUPPRESS and zone == "low" and status in ("PROMOTE", "PROMOTE_TOLERANCE"):
        return "MEASURING"
    return status


def _threeway_pick_label(zone: str) -> str:
    """Human-readable pick label for the 3-way market (all zones: alpha-or-draw)."""
    return "Alpha Win or Draw"


# ---------------------------------------------------------------------------
# Cell computation
# ---------------------------------------------------------------------------

def _compute_cells(rows: list[dict]) -> list[dict[str, Any]]:
    """Build per-(zone × bts_pocket) cell statistics from fixture rows.

    Each row must contain: draw_odd, btts_yes_odd, btts_no_odd, home_odd,
    away_odd, home_score, away_score, home_corners, away_corners, tier.

    Re-Foundation partition: 2-key ``(zone, bts_pocket)``. DF is a signal, not a
    cell axis — DF/H2H splits are reported separately (the test signal tables),
    not here.

    Returns list of cell dicts (unsorted, promotion ranks not yet assigned).
    """
    # Accumulator: keyed by (zone, bts_pocket)
    acc: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        zone = zone_of(row.get("draw_odd"))
        bts = bts_of(row.get("btts_yes_odd"), row.get("btts_no_odd"))
        if zone is None or bts is None:
            continue

        key = (zone, bts)
        if key not in acc:
            acc[key] = {
                "zone": zone,
                "bts_pocket": bts,
                "n": 0,
                "gn_green": 0,  # goals natural line
                "gs_green": 0,  # goals system line
                "cn_green": 0,  # corners natural
                "cs_green": 0,  # corners system
                "tw_green": 0,  # threeway
            }

        cell = acc[key]
        cell["n"] += 1

        gn = natural_line(zone, "goals")
        gs = system_line(zone, "goals")
        cn = natural_line(zone, "corners")
        cs = system_line(zone, "corners")

        if _goals_green(row, gn):
            cell["gn_green"] += 1
        if _goals_green(row, gs):
            cell["gs_green"] += 1
        if _corners_green(row, cn):
            cell["cn_green"] += 1
        if _corners_green(row, cs):
            cell["cs_green"] += 1
        if _threeway_green(row, zone):
            cell["tw_green"] += 1

    # Convert raw counts to hit-rate dicts
    result: list[dict[str, Any]] = []
    total_n = sum(c["n"] for c in acc.values())

    for (zone, bts), cell in acc.items():
        n = cell["n"]
        gn_hit = _hit_rate(cell["gn_green"], n)
        gs_hit = _hit_rate(cell["gs_green"], n)
        cn_hit = _hit_rate(cell["cn_green"], n)
        cs_hit = _hit_rate(cell["cs_green"], n)
        tw_hit = _hit_rate(cell["tw_green"], n)

        goals_drop = round(gn_hit - gs_hit, 4)
        corners_drop = round(cn_hit - cs_hit, 4)

        result.append({
            "zone": zone,
            "bts_pocket": bts,
            "n_fixtures": n,
            "n_pct_of_zone": round(n / total_n * 100, 2) if total_n else 0.0,
            "gn_hit": round(gn_hit, 2),
            "gs_hit": round(gs_hit, 2),
            "cn_hit": round(cn_hit, 2),
            "cs_hit": round(cs_hit, 2),
            "threeway_hit": round(tw_hit, 2),
            "goals_1up_drop": goals_drop,
            "corners_1up_drop": corners_drop,
            # ranks and promote set in next pass
            "goals_drop_rank": None,
            "corners_drop_rank": None,
            "goals_promote": "NO",
            "corners_promote": "NO",
            "threeway_promote": "NO",
            "cell_promoted": False,
            "threeway_pick": _threeway_pick_label(zone),
        })

    return result


def _assign_ranks_and_promotion(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign drop ranks within each zone and apply promotion framework.

    Mutates cells in-place and returns the list.
    """
    # Group cells by zone for rank assignment
    from collections import defaultdict

    zone_cells: dict[str, list[dict]] = defaultdict(list)
    for cell in cells:
        zone_cells[cell["zone"]].append(cell)

    for zone, group in zone_cells.items():
        # --- Goals drop rank (ascending = least drop = rank 1) ---
        sorted_g = sorted(group, key=lambda c: c["goals_1up_drop"])
        for rank, cell in enumerate(sorted_g, start=1):
            cell["goals_drop_rank"] = rank
        rank1_g_drop = sorted_g[0]["goals_1up_drop"] if sorted_g else 0.0

        # --- Corners drop rank ---
        sorted_c = sorted(group, key=lambda c: c["corners_1up_drop"])
        for rank, cell in enumerate(sorted_c, start=1):
            cell["corners_drop_rank"] = rank
        rank1_c_drop = sorted_c[0]["corners_1up_drop"] if sorted_c else 0.0

        # --- Apply promotion ---
        for cell in group:
            cell["goals_promote"] = _promote_status(
                cell["gn_hit"],
                cell["goals_1up_drop"],
                cell["goals_drop_rank"],
                rank1_g_drop,
                zone,
            )
            cell["corners_promote"] = _promote_status(
                cell["cn_hit"],
                cell["corners_1up_drop"],
                cell["corners_drop_rank"],
                rank1_c_drop,
                zone,
            )
            cell["threeway_promote"] = _threeway_promote_status(
                cell["threeway_hit"], zone
            )
            cell["cell_promoted"] = any(
                s in ("PROMOTE", "PROMOTE_TOLERANCE")
                for s in (
                    cell["goals_promote"],
                    cell["corners_promote"],
                    cell["threeway_promote"],
                )
            )

    return cells


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_foundation(rows: list[dict]) -> dict[str, Any]:
    """Compute the Foundation Matrix from settled fixture rows.

    Produces three tier splits (all / t1t2 / t3) each containing a list of
    cell dicts with hit rates and promotion statuses.

    Args:
        rows: Settled fixture rows. Each must include draw_odd,
              btts_yes_odd, btts_no_odd, home_score, away_score,
              home_corners, away_corners, home_odd, away_odd, tier.

    Returns:
        Dict with keys ``all``, ``t1t2``, ``t3``, and ``summary``.
    """
    t1t2_rows = [r for r in rows if r.get("tier") in (1, 2)]
    t3_rows = [r for r in rows if r.get("tier") == 3]

    cells_all = _assign_ranks_and_promotion(_compute_cells(rows))
    cells_t1t2 = _assign_ranks_and_promotion(_compute_cells(t1t2_rows))
    cells_t3 = _assign_ranks_and_promotion(_compute_cells(t3_rows))

    promoted_count = sum(
        1 for c in cells_all
        if c["threeway_promote"] in ("PROMOTE", "PROMOTE_TOLERANCE")
    )

    return {
        "all": cells_all,
        "t1t2": cells_t1t2,
        "t3": cells_t3,
        "summary": {
            "total_fixtures": len(rows),
            "promoted_cells": promoted_count,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
    }
