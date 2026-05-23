"""OddsFlow V3 — Database helpers.

Provides init_db (schema creation + migrations) and get_conn (connection factory).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: str) -> None:
    """Create all tables and run additive migrations.

    Safe to call on both fresh and existing databases — all DDL is
    idempotent (CREATE IF NOT EXISTS / ALTER IF missing column).
    """
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        _run_migrations(conn)
        conn.commit()
    finally:
        conn.close()


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Additive ALTER TABLE migrations for existing databases.

    Each statement is wrapped in try/except so that columns already
    present (fresh DB or re-run) are silently skipped.
    """
    additive = [
        "ALTER TABLE leagues ADD COLUMN sportmonks_id INTEGER",
        "ALTER TABLE teams   ADD COLUMN sportmonks_id INTEGER",
        "ALTER TABLE teams   ADD COLUMN short_name    TEXT",
        "ALTER TABLE fixtures ADD COLUMN sportmonks_id INTEGER",
        # emit_log additions for V4
        "ALTER TABLE emit_log ADD COLUMN partition_key TEXT",
        "ALTER TABLE emit_log ADD COLUMN strategy      TEXT",
        # system_health table (if not in schema.sql)
        # pick_results outcome column (ensure it exists)
    ]
    for ddl in additive:
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass  # column already exists

    indexes = [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_leagues_smid  ON leagues(sportmonks_id)  WHERE sportmonks_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_teams_smid    ON teams(sportmonks_id)    WHERE sportmonks_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fixtures_smid ON fixtures(sportmonks_id) WHERE sportmonks_id IS NOT NULL",
    ]
    for ddl in indexes:
        conn.execute(ddl)


def get_conn(db_path: str) -> sqlite3.Connection:
    """Return a sqlite3 connection with Row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
