"""OddsFlow V3 — Foundation data loader.

Queries settled fixtures with stats from the V3 database and returns
rows ready for compute_foundation().
"""

from __future__ import annotations

import sqlite3
from typing import Any


_QUERY = """
SELECT
    f.draw_odd,
    f.btts_yes_odd,
    f.btts_no_odd,
    f.home_odd,
    f.away_odd,
    f.home_score,
    f.away_score,
    f.tier,
    fs.home_corners,
    fs.away_corners
FROM fixtures f
LEFT JOIN fixture_stats fs ON fs.fixture_id = f.id
WHERE f.home_score       IS NOT NULL
  AND f.away_score       IS NOT NULL
  AND f.draw_odd         IS NOT NULL
  AND f.btts_yes_odd     IS NOT NULL
  AND f.btts_no_odd      IS NOT NULL
  AND f.home_odd         IS NOT NULL
  AND f.away_odd         IS NOT NULL
"""


def load_foundation(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Load all settled, fully-odds-populated fixtures from the database.

    Args:
        conn: An open sqlite3.Connection (row_factory=sqlite3.Row recommended).

    Returns:
        List of dicts with keys: draw_odd, btts_yes_odd, btts_no_odd,
        home_odd, away_odd, home_score, away_score, tier,
        home_corners, away_corners.
    """
    cursor = conn.execute(_QUERY)
    rows = cursor.fetchall()
    # Convert sqlite3.Row (or plain tuple) to plain dicts
    return [dict(row) for row in rows]
