"""OddsFlow V3 — Seed script.

Reads the V2 calibration database (read-only) and copies fixtures,
fixture_stats, h2h_meetings, and leagues into the V3 database.

Usage:
    python scripts/seed_from_calibration.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

V2_DB = "C:/OddsFlowV4/data/v1_calibration_readonly.db"
V3_DB = "C:/OddsFlowV4/data/oddsflow_v4.db"


def _count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return row[0] if row else 0


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Return column names present in *table* for this connection."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def seed() -> None:
    src = sqlite3.connect(f"file:{V2_DB}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row

    # Ensure V3 DB directory exists and schema is applied
    Path(V3_DB).parent.mkdir(parents=True, exist_ok=True)

    # Import schema before opening dst
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app.db.database import init_db
    init_db(V3_DB)

    dst = sqlite3.connect(V3_DB)
    dst.row_factory = sqlite3.Row

    # ------------------------------------------------------------------ #
    # Print before counts
    # ------------------------------------------------------------------ #
    print("=== BEFORE (V3 counts) ===")
    for tbl in ("leagues", "fixtures", "fixture_stats", "h2h_meetings"):
        try:
            print(f"  {tbl}: {_count(dst, tbl)}")
        except Exception:
            print(f"  {tbl}: (table missing)")

    # ------------------------------------------------------------------ #
    # leagues
    # ------------------------------------------------------------------ #
    src_leagues_cols = _table_columns(src, "leagues")
    dst_leagues_cols = _table_columns(dst, "leagues")
    shared_leagues = [c for c in dst_leagues_cols if c in src_leagues_cols]

    leagues_rows = src.execute(
        f"SELECT {', '.join(shared_leagues)} FROM leagues"
    ).fetchall()

    placeholders = ", ".join("?" * len(shared_leagues))
    col_list = ", ".join(shared_leagues)
    dst.executemany(
        f"INSERT OR IGNORE INTO leagues ({col_list}) VALUES ({placeholders})",
        [tuple(r[c] for c in shared_leagues) for r in leagues_rows],
    )
    print(f"\nLeagues inserted/ignored: {len(leagues_rows)}")

    # ------------------------------------------------------------------ #
    # fixtures  (status forced to 'settled' — all calibration rows have scores)
    # ------------------------------------------------------------------ #
    src_fix_cols = _table_columns(src, "fixtures")
    dst_fix_cols = _table_columns(dst, "fixtures")
    shared_fix = [c for c in dst_fix_cols if c in src_fix_cols and c != "status"]

    fixture_rows = src.execute(
        f"SELECT {', '.join(shared_fix)} FROM fixtures"
    ).fetchall()

    # Build insert with status='settled' injected
    insert_cols = shared_fix + ["status"]
    placeholders = ", ".join("?" * len(insert_cols))
    col_list = ", ".join(insert_cols)

    dst.executemany(
        f"INSERT OR IGNORE INTO fixtures ({col_list}) VALUES ({placeholders})",
        [tuple(r[c] for c in shared_fix) + ("settled",) for r in fixture_rows],
    )
    print(f"Fixtures inserted/ignored: {len(fixture_rows)}")

    # ------------------------------------------------------------------ #
    # fixture_stats
    # ------------------------------------------------------------------ #
    src_stats_cols = _table_columns(src, "fixture_stats")
    dst_stats_cols = _table_columns(dst, "fixture_stats")
    shared_stats = [c for c in dst_stats_cols if c in src_stats_cols]

    stats_rows = src.execute(
        f"SELECT {', '.join(shared_stats)} FROM fixture_stats"
    ).fetchall()

    placeholders = ", ".join("?" * len(shared_stats))
    col_list = ", ".join(shared_stats)
    dst.executemany(
        f"INSERT OR IGNORE INTO fixture_stats ({col_list}) VALUES ({placeholders})",
        [tuple(r[c] for c in shared_stats) for r in stats_rows],
    )
    print(f"Fixture stats inserted/ignored: {len(stats_rows)}")

    # ------------------------------------------------------------------ #
    # h2h_meetings
    # ------------------------------------------------------------------ #
    src_h2h_cols = _table_columns(src, "h2h_meetings")
    dst_h2h_cols = _table_columns(dst, "h2h_meetings")
    shared_h2h = [c for c in dst_h2h_cols if c in src_h2h_cols]

    h2h_rows = src.execute(
        f"SELECT {', '.join(shared_h2h)} FROM h2h_meetings"
    ).fetchall()

    placeholders = ", ".join("?" * len(shared_h2h))
    col_list = ", ".join(shared_h2h)
    dst.executemany(
        f"INSERT OR IGNORE INTO h2h_meetings ({col_list}) VALUES ({placeholders})",
        [tuple(r[c] for c in shared_h2h) for r in h2h_rows],
    )
    print(f"H2H meetings inserted/ignored: {len(h2h_rows)}")

    dst.commit()
    src.close()

    # ------------------------------------------------------------------ #
    # Print after counts
    # ------------------------------------------------------------------ #
    print("\n=== AFTER (V3 counts) ===")
    for tbl in ("leagues", "fixtures", "fixture_stats", "h2h_meetings"):
        print(f"  {tbl}: {_count(dst, tbl)}")

    dst.close()
    print("\nSeed complete.")


if __name__ == "__main__":
    seed()
