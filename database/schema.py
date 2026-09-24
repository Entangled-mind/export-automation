"""Database schema and index definition for Phase 5 SQLite migration.

Creates normalized relational tables and performance indices for:
- buyers (master catalog)
- classifications (AI evaluation, tiers, intent scores)
- outreach_logs (dispatch history, delivery outcomes)
- activity_logs (audit trails, system events)
"""

from pathlib import Path
from typing import Optional

import config
from database.connection import db_session

SCHEMA_DDL = """
-- 1. Master Buyers Table
CREATE TABLE IF NOT EXISTS buyers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_name TEXT,
    company_name TEXT,
    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
    website TEXT,
    country TEXT,
    source_platform TEXT,
    quality_status TEXT DEFAULT 'VALID',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 2. AI Classifications Table
CREATE TABLE IF NOT EXISTS classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id INTEGER REFERENCES buyers(id) ON DELETE CASCADE,
    email TEXT NOT NULL COLLATE NOCASE,
    category TEXT NOT NULL,
    tier TEXT NOT NULL,
    intent_score INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.0,
    outreach_angle TEXT,
    reasoning TEXT,
    source TEXT DEFAULT 'Heuristic',
    created_at TEXT DEFAULT (datetime('now'))
);

-- 3. Outreach Logs Table
CREATE TABLE IF NOT EXISTS outreach_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id INTEGER REFERENCES buyers(id) ON DELETE SET NULL,
    email TEXT NOT NULL COLLATE NOCASE,
    status TEXT NOT NULL,
    subject TEXT,
    message TEXT,
    timestamp TEXT DEFAULT (datetime('now'))
);

-- 4. Activity Audit Logs Table
CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    event TEXT NOT NULL,
    email TEXT,
    status TEXT,
    message TEXT
);

-- Performance Indices
CREATE INDEX IF NOT EXISTS idx_buyers_email ON buyers(email);
CREATE INDEX IF NOT EXISTS idx_buyers_company ON buyers(company_name);
CREATE INDEX IF NOT EXISTS idx_classifications_email ON classifications(email);
CREATE INDEX IF NOT EXISTS idx_classifications_tier ON classifications(tier);
CREATE INDEX IF NOT EXISTS idx_classifications_category ON classifications(category);
CREATE INDEX IF NOT EXISTS idx_outreach_email ON outreach_logs(email);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_logs(status);
CREATE INDEX IF NOT EXISTS idx_outreach_timestamp ON outreach_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_activity_event ON activity_logs(event);
CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity_logs(timestamp);
"""


def init_database(db_path: Optional[Path] = None) -> Path:
    """Execute DDL statements to initialize all database tables and indices.

    Args:
        db_path: Optional custom path to SQLite database. Defaults to config.DB_PATH.

    Returns:
        Path to the initialized database file.
    """
    path = db_path if db_path is not None else config.DB_PATH
    with db_session(path) as conn:
        conn.executescript(SCHEMA_DDL)
    return path
