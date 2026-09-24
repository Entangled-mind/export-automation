"""Data Access Object (DAO) Repository layer for Phase 5 SQLite database.

Provides parameterized, transaction-safe queries for buyers, classifications,
outreach logs, and audit trails.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from database.connection import db_session
from extraction.data_extractor import normalize_email


# ==============================================================================
# BUYER REPOSITORY
# ==============================================================================
def upsert_buyer(buyer_data: Dict[str, Any], db_path: Optional[Path] = None) -> int:
    """Insert or update a buyer record in the buyers table.

    Args:
        buyer_data: Dictionary containing buyer attributes.
        db_path: Optional custom database path.

    Returns:
        Integer primary key ID of the inserted or updated buyer.
    """
    email = normalize_email(buyer_data.get("email"))
    if not email:
        raise ValueError("Cannot persist buyer: email address is required.")

    name = (buyer_data.get("buyer_name") or "").strip()
    company = (buyer_data.get("company_name") or "").strip()
    website = (buyer_data.get("website") or "").strip()
    country = (buyer_data.get("country") or "").strip()
    platform = (buyer_data.get("source_platform") or "").strip()
    quality = (buyer_data.get("quality_status") or "VALID").strip()

    sql = """
    INSERT INTO buyers (buyer_name, company_name, email, website, country, source_platform, quality_status, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ON CONFLICT(email) DO UPDATE SET
        buyer_name = CASE WHEN excluded.buyer_name != '' THEN excluded.buyer_name ELSE buyers.buyer_name END,
        company_name = CASE WHEN excluded.company_name != '' THEN excluded.company_name ELSE buyers.company_name END,
        website = CASE WHEN excluded.website != '' THEN excluded.website ELSE buyers.website END,
        country = CASE WHEN excluded.country != '' THEN excluded.country ELSE buyers.country END,
        source_platform = CASE WHEN excluded.source_platform != '' THEN excluded.source_platform ELSE buyers.source_platform END,
        quality_status = excluded.quality_status,
        updated_at = datetime('now')
    RETURNING id;
    """
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (name, company, email, website, country, platform, quality))
        row = cursor.fetchone()
        return row["id"] if row else cursor.lastrowid


def get_buyer_by_email(email: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a buyer record by email address.

    Args:
        email: Email to search.
        db_path: Optional custom database path.

    Returns:
        Dictionary of buyer fields or None if not found.
    """
    clean_email = normalize_email(email)
    sql = "SELECT * FROM buyers WHERE email = ? COLLATE NOCASE;"
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (clean_email,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_buyers(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retrieve all buyer records ordered by ID ascending.

    Args:
        db_path: Optional custom database path.

    Returns:
        List of buyer dictionaries.
    """
    sql = "SELECT * FROM buyers ORDER BY id ASC;"
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        return [dict(row) for row in cursor.fetchall()]


# ==============================================================================
# CLASSIFICATION REPOSITORY
# ==============================================================================
def save_classification(
    email: str,
    category: str,
    tier: str,
    intent_score: int = 0,
    confidence: float = 0.0,
    outreach_angle: str = "",
    reasoning: str = "",
    source: str = "Heuristic",
    buyer_id: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Insert or update an AI classification record.

    Args:
        email: Target email address.
        category: 'BUSINESS', 'INDIVIDUAL', or 'IRRELEVANT'.
        tier: Priority tier string.
        intent_score: 0 to 100 intent score.
        confidence: 0.0 to 1.0 confidence score.
        outreach_angle: Tailored outreach angle.
        reasoning: Explanation rationale.
        source: Classification engine source ('Gemini AI', 'Heuristic', etc.).
        buyer_id: Optional foreign key to buyers table.
        db_path: Optional custom database path.

    Returns:
        Primary key ID of the classification record.
    """
    clean_email = normalize_email(email)

    with db_session(db_path) as conn:
        cursor = conn.cursor()

        # If buyer_id is not given, resolve it
        if buyer_id is None:
            cursor.execute("SELECT id FROM buyers WHERE email = ? COLLATE NOCASE;", (clean_email,))
            b_row = cursor.fetchone()
            if b_row:
                buyer_id = b_row["id"]

        # Check for existing classification for this email
        cursor.execute("SELECT id FROM classifications WHERE email = ? COLLATE NOCASE;", (clean_email,))
        existing = cursor.fetchone()

        if existing:
            update_sql = """
            UPDATE classifications
            SET buyer_id = COALESCE(?, buyer_id),
                category = ?,
                tier = ?,
                intent_score = ?,
                confidence = ?,
                outreach_angle = ?,
                reasoning = ?,
                source = ?,
                created_at = datetime('now')
            WHERE id = ?;
            """
            cursor.execute(
                update_sql,
                (buyer_id, category, tier, intent_score, confidence, outreach_angle, reasoning, source, existing["id"]),
            )
            return existing["id"]
        else:
            insert_sql = """
            INSERT INTO classifications (buyer_id, email, category, tier, intent_score, confidence, outreach_angle, reasoning, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'));
            """
            cursor.execute(
                insert_sql,
                (buyer_id, clean_email, category, tier, intent_score, confidence, outreach_angle, reasoning, source),
            )
            return cursor.lastrowid


def get_classification_by_email(email: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve classification record for a given email address.

    Args:
        email: Email to look up.
        db_path: Optional custom database path.

    Returns:
        Dictionary of classification record or None.
    """
    clean_email = normalize_email(email)
    sql = "SELECT * FROM classifications WHERE email = ? COLLATE NOCASE;"
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (clean_email,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_classifications(
    category: Optional[str] = None,
    tier: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Retrieve classifications with optional filtering by category or tier.

    Args:
        category: Optional category filter.
        tier: Optional tier filter.
        db_path: Optional custom database path.

    Returns:
        List of classification dictionaries joined with buyer details.
    """
    sql = """
    SELECT c.*, b.buyer_name, b.company_name, b.website, b.country
    FROM classifications c
    LEFT JOIN buyers b ON c.email = b.email
    WHERE 1=1
    """
    params = []
    if category:
        sql += " AND c.category = ?"
        params.append(category.strip().upper())
    if tier:
        sql += " AND c.tier = ?"
        params.append(tier.strip())

    sql += " ORDER BY c.intent_score DESC, c.id ASC;"

    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


# ==============================================================================
# OUTREACH LOG REPOSITORY
# ==============================================================================
def record_outreach(
    email: str,
    status: str,
    subject: str = "",
    message: str = "",
    buyer_id: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Record an outreach attempt in outreach_logs table.

    Args:
        email: Recipient email address.
        status: Delivery status ('SUCCESS', 'SIMULATED_SUCCESS', 'FAILED', etc.).
        subject: Subject line.
        message: Delivery notes or error message.
        buyer_id: Optional foreign key to buyers table.
        db_path: Optional custom database path.

    Returns:
        Primary key ID of the inserted outreach log.
    """
    clean_email = normalize_email(email)
    now_ts = datetime.now().isoformat(timespec="seconds")

    with db_session(db_path) as conn:
        cursor = conn.cursor()
        if buyer_id is None:
            cursor.execute("SELECT id FROM buyers WHERE email = ? COLLATE NOCASE;", (clean_email,))
            b_row = cursor.fetchone()
            if b_row:
                buyer_id = b_row["id"]

        sql = """
        INSERT INTO outreach_logs (buyer_id, email, status, subject, message, timestamp)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        cursor.execute(sql, (buyer_id, clean_email, status.strip().upper(), subject, message, now_ts))
        return cursor.lastrowid


def is_email_contacted(email: str, db_path: Optional[Path] = None) -> bool:
    """Check if an email has already been successfully contacted.

    Args:
        email: Email to verify.
        db_path: Optional custom database path.

    Returns:
        True if a SUCCESS or SIMULATED_SUCCESS record exists, False otherwise.
    """
    clean_email = normalize_email(email)
    sql = """
    SELECT 1 FROM outreach_logs
    WHERE email = ? COLLATE NOCASE AND status IN ('SUCCESS', 'SIMULATED_SUCCESS')
    LIMIT 1;
    """
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (clean_email,))
        return cursor.fetchone() is not None


def get_outreach_history(limit: int = 100, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retrieve recent outreach logs.

    Args:
        limit: Maximum number of rows to return.
        db_path: Optional custom database path.

    Returns:
        List of outreach dictionaries.
    """
    sql = "SELECT * FROM outreach_logs ORDER BY id DESC LIMIT ?;"
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_today_outreach_count(db_path: Optional[Path] = None) -> int:
    """Count emails dispatched today from outreach_logs table.

    Args:
        db_path: Optional custom database path.

    Returns:
        Count of successful/simulated dispatches for the current calendar date.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    sql = """
    SELECT COUNT(*) as count FROM outreach_logs
    WHERE timestamp LIKE ? AND status IN ('SUCCESS', 'SIMULATED_SUCCESS');
    """
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (f"{today_str}%",))
        row = cursor.fetchone()
        return row["count"] if row else 0


# ==============================================================================
# ACTIVITY AUDIT REPOSITORY
# ==============================================================================
def record_activity(
    event: str,
    email: str = "",
    status: str = "",
    message: str = "",
    db_path: Optional[Path] = None,
) -> int:
    """Record an audit trail event in activity_logs table.

    Args:
        event: Event name.
        email: Target email or empty string.
        status: Event status.
        message: Audit message details.
        db_path: Optional custom database path.

    Returns:
        Primary key ID of the inserted activity log.
    """
    clean_email = normalize_email(email)
    now_ts = datetime.now().isoformat(timespec="seconds")
    sql = """
    INSERT INTO activity_logs (timestamp, event, email, status, message)
    VALUES (?, ?, ?, ?, ?);
    """
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (now_ts, event.strip(), clean_email, status.strip(), message.strip()))
        return cursor.lastrowid


def get_activity_logs(limit: int = 100, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retrieve recent activity audit logs.

    Args:
        limit: Maximum number of rows to return.
        db_path: Optional custom database path.

    Returns:
        List of activity log dictionaries.
    """
    sql = "SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?;"
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (limit,))
        return [dict(row) for row in cursor.fetchall()]


# ==============================================================================
# DATABASE SUMMARY STATS
# ==============================================================================
def get_database_stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Calculate aggregated KPI metrics across all database tables.

    Args:
        db_path: Optional custom database path.

    Returns:
        Dictionary of counts and breakdowns.
    """
    with db_session(db_path) as conn:
        cursor = conn.cursor()

        # Total buyers
        cursor.execute("SELECT COUNT(*) as c FROM buyers;")
        total_buyers = cursor.fetchone()["c"]

        # Classifications breakdown
        cursor.execute("SELECT category, COUNT(*) as c FROM classifications GROUP BY category;")
        cat_counts = {row["category"]: row["c"] for row in cursor.fetchall()}

        cursor.execute("SELECT tier, COUNT(*) as c FROM classifications GROUP BY tier;")
        tier_counts = {row["tier"]: row["c"] for row in cursor.fetchall()}

        # Outreach breakdown
        cursor.execute("SELECT status, COUNT(*) as c FROM outreach_logs GROUP BY status;")
        outreach_counts = {row["status"]: row["c"] for row in cursor.fetchall()}

        # Total activity events
        cursor.execute("SELECT COUNT(*) as c FROM activity_logs;")
        total_activities = cursor.fetchone()["c"]

        return {
            "total_buyers": total_buyers,
            "business_buyers": cat_counts.get("BUSINESS", 0),
            "individual_buyers": cat_counts.get("INDIVIDUAL", 0),
            "irrelevant_buyers": cat_counts.get("IRRELEVANT", 0),
            "tier_1_count": tier_counts.get(config.TIER_1, 0),
            "tier_2_count": tier_counts.get(config.TIER_2, 0),
            "tier_3_count": tier_counts.get(config.TIER_3, 0),
            "outreach_success": outreach_counts.get("SUCCESS", 0),
            "outreach_simulated": outreach_counts.get("SIMULATED_SUCCESS", 0),
            "outreach_failed": outreach_counts.get("FAILED", 0),
            "total_activities": total_activities,
        }
