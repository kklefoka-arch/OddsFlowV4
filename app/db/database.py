"""OddsFlow V3 — Database helpers.

Provides init_db (schema creation) and get_conn (connection factory).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: str) -> None:
    """Create all tables defined in schema.sql if they do not exist.

    Args:
        db_path: Filesystem path to the SQLite database file.
    """
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def get_conn(db_path: str) -> sqlite3.Connection:
    """Return a sqlite3 connection with Row factory enabled.

    Args:
        db_path: Filesystem path to the SQLite database file.

    Returns:
        An open sqlite3.Connection whose rows behave like dicts.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
