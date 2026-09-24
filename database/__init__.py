"""Database package for EXPORT Automation System (Phase 5: SQLite Database)."""

from .connection import db_session, get_connection
from .migration import migrate_csv_to_sqlite
from .repository import (
    get_activity_logs,
    get_all_buyers,
    get_all_classifications,
    get_buyer_by_email,
    get_classification_by_email,
    get_database_stats,
    get_outreach_history,
    get_today_outreach_count,
    is_email_contacted,
    record_activity,
    record_outreach,
    save_classification,
    upsert_buyer,
)
from .schema import init_database

__all__ = [
    "get_connection",
    "db_session",
    "init_database",
    "upsert_buyer",
    "get_buyer_by_email",
    "get_all_buyers",
    "save_classification",
    "get_classification_by_email",
    "get_all_classifications",
    "record_outreach",
    "is_email_contacted",
    "get_outreach_history",
    "get_today_outreach_count",
    "record_activity",
    "get_activity_logs",
    "get_database_stats",
    "migrate_csv_to_sqlite",
]
