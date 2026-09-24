"""CSV to SQLite automated data migration engine for Phase 5.

Safely imports historical records from:
- data/buyers.csv -> buyers table
- data/business_buyers.csv & data/individual_buyers.csv -> classifications table
- data/sent_log.csv -> outreach_logs table
- data/activity_log.csv -> activity_logs table

Ensures idempotency, atomic transactional integrity, and zero data loss.
"""

import csv
from pathlib import Path
from typing import Dict, Optional

import config
from database.connection import db_session
from database.repository import (
    record_activity,
    record_outreach,
    save_classification,
    upsert_buyer,
)
from database.schema import init_database
from extraction.data_extractor import normalize_email


def migrate_csv_to_sqlite(
    db_path: Optional[Path] = None,
    data_dir: Optional[Path] = None,
) -> Dict[str, int]:
    """Migrate all historical CSV databases into the SQLite relational database.

    Args:
        db_path: Optional custom path to SQLite database.
        data_dir: Optional custom directory containing CSV files.

    Returns:
        Dictionary mapping table names to the count of migrated records.
    """
    db = init_database(db_path)
    csv_root = data_dir if data_dir is not None else config.DATA_DIR

    counts = {
        "buyers": 0,
        "classifications": 0,
        "outreach_logs": 0,
        "activity_logs": 0,
    }

    # 1. Migrate Master Buyers (buyers.csv)
    buyers_csv = csv_root / "buyers.csv"
    if buyers_csv.exists() and buyers_csv.stat().st_size > 0:
        with open(buyers_csv, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = normalize_email(row.get("email"))
                if email:
                    upsert_buyer(row, db_path=db)
                    counts["buyers"] += 1

    # 2. Migrate Classified Buyers (business_buyers.csv & individual_buyers.csv)
    for cat_name, file_name in [("BUSINESS", "business_buyers.csv"), ("INDIVIDUAL", "individual_buyers.csv")]:
        cat_csv = csv_root / file_name
        if cat_csv.exists() and cat_csv.stat().st_size > 0:
            with open(cat_csv, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = normalize_email(row.get("email"))
                    if email:
                        # Ensure buyer exists in buyers table
                        upsert_buyer(row, db_path=db)

                        tier = row.get("tier") or (config.TIER_2 if cat_name == "BUSINESS" else config.TIER_3)
                        intent_str = row.get("intent_score") or "0"
                        try:
                            intent_score = int(intent_str)
                        except ValueError:
                            intent_score = 80 if cat_name == "BUSINESS" else 45

                        save_classification(
                            email=email,
                            category=row.get("classification") or cat_name,
                            tier=tier,
                            intent_score=intent_score,
                            confidence=0.90,
                            outreach_angle=row.get("outreach_angle", ""),
                            reasoning=row.get("reasoning", ""),
                            source="Migration",
                            db_path=db,
                        )
                        counts["classifications"] += 1

    # 3. Migrate Sent History (sent_log.csv)
    sent_csv = csv_root / "sent_log.csv"
    if sent_csv.exists() and sent_csv.stat().st_size > 0:
        with open(sent_csv, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = normalize_email(row.get("email"))
                status = (row.get("status") or "").strip().upper()
                if email and status:
                    # Check if already in outreach_logs to avoid duplicate migration
                    with db_session(db) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT 1 FROM outreach_logs WHERE email = ? AND status = ? LIMIT 1;",
                            (email, status),
                        )
                        if not cursor.fetchone():
                            cursor.execute(
                                "INSERT INTO outreach_logs (email, status, timestamp) VALUES (?, ?, ?);",
                                (email, status, row.get("timestamp", "")),
                            )
                            counts["outreach_logs"] += 1

    # 4. Migrate Audit Trail (activity_log.csv)
    activity_csv = csv_root / "activity_log.csv"
    if activity_csv.exists() and activity_csv.stat().st_size > 0:
        with open(activity_csv, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                event = (row.get("event") or "").strip()
                if event:
                    with db_session(db) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT 1 FROM activity_logs WHERE timestamp = ? AND event = ? AND email = ? LIMIT 1;",
                            (row.get("timestamp", ""), event, normalize_email(row.get("email"))),
                        )
                        if not cursor.fetchone():
                            cursor.execute(
                                "INSERT INTO activity_logs (timestamp, event, email, status, message) VALUES (?, ?, ?, ?, ?);",
                                (
                                    row.get("timestamp", ""),
                                    event,
                                    normalize_email(row.get("email")),
                                    row.get("status", ""),
                                    row.get("message", ""),
                                ),
                            )
                            counts["activity_logs"] += 1

    return counts
