"""Database connection and transaction management for Phase 5 SQLite migration.

Provides connection pooling, row factory configuration, and transaction context managers.
"""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Generator, Optional

import config


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Create and configure a new SQLite database connection.

    Args:
        db_path: Optional custom path to SQLite database. Defaults to config.DB_PATH.

    Returns:
        Configured sqlite3.Connection with Row factory and foreign keys enabled.
    """
    path = db_path if db_path is not None else config.DB_PATH
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_session(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager providing an atomic transactional database session.

    Commits on successful completion, rollbacks on error, and ensures the connection is closed.

    Args:
        db_path: Optional custom path to SQLite database.

    Yields:
        sqlite3.Connection instance.
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
