"""Activity and outreach logging module for EXPORT Automation System.

Manages audit trails for Phase 1 events and tracks outreach history in sent_log.csv.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import config
from extraction.data_extractor import normalize_email

SENT_LOG_FIELDS = ["email", "status", "timestamp"]
ACTIVITY_LOG_FIELDS = ["timestamp", "event", "email", "status", "message"]


def init_sent_log(csv_path: Optional[Path] = None) -> Path:
    """Initialize sent_log.csv file with headers if it does not already exist.

    Args:
        csv_path: Optional custom path for sent_log.csv. Defaults to config.SENT_LOG_CSV.

    Returns:
        Path to the initialized sent_log.csv file.
    """
    path = Path(csv_path) if csv_path else config.SENT_LOG_CSV
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists() or path.stat().st_size == 0:
        with open(path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=SENT_LOG_FIELDS)
            writer.writeheader()
    return path


def log_sent_entry(
    email: str, status: str, csv_path: Optional[Path] = None
) -> None:
    """Record an email outreach attempt in sent_log.csv.

    Possible status values for Phase 1 testing:
    - SUCCESS
    - FAILED
    - SKIPPED_DUPLICATE

    Args:
        email: Email address targeted.
        status: Result status of the outreach.
        csv_path: Optional custom path for sent_log.csv.
    """
    cleaned_email = normalize_email(email)
    path = init_sent_log(csv_path)

    entry = {
        "email": cleaned_email,
        "status": status.strip().upper(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    with open(path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SENT_LOG_FIELDS)
        writer.writerow(entry)


def read_sent_history(csv_path: Optional[Path] = None) -> List[Dict[str, str]]:
    """Read all entries from sent_log.csv.

    Args:
        csv_path: Optional custom path for sent_log.csv.

    Returns:
        List of dictionaries with email, status, and timestamp keys.
    """
    path = init_sent_log(csv_path)
    entries: List[Dict[str, str]] = []

    with open(path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append({
                "email": normalize_email(row.get("email")),
                "status": (row.get("status") or "").strip().upper(),
                "timestamp": (row.get("timestamp") or "").strip(),
            })
    return entries


def is_sent_successfully(email: str, csv_path: Optional[Path] = None) -> bool:
    """Check whether an email has already been successfully sent to (case-insensitive).

    Args:
        email: Email to check.
        csv_path: Optional custom path for sent_log.csv.

    Returns:
        True if the email has a SUCCESS entry in sent_log.csv, False otherwise.
    """
    target = normalize_email(email)
    if not target:
        return False

    history = read_sent_history(csv_path)
    for entry in history:
        if entry["email"] == target and entry["status"] == "SUCCESS":
            return True
    return False


def init_activity_log(csv_path: Optional[Path] = None) -> Path:
    """Initialize activity_log.csv file with headers if it does not already exist.

    Args:
        csv_path: Optional custom path for activity_log.csv. Defaults to config.ACTIVITY_LOG_CSV.

    Returns:
        Path to the initialized activity_log.csv file.
    """
    path = Path(csv_path) if csv_path else config.ACTIVITY_LOG_CSV
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists() or path.stat().st_size == 0:
        with open(path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ACTIVITY_LOG_FIELDS)
            writer.writeheader()
    return path


def log_activity(
    event: str,
    email: str,
    status: str,
    message: str,
    csv_path: Optional[Path] = None,
    print_console: bool = True,
) -> None:
    """Log an event to activity_log.csv and optionally print to console.

    Args:
        event: Category or name of event (e.g. VALIDATION, DUPLICATE_CHECK).
        email: Associated email address (or empty string).
        status: Outcome status (e.g. SUCCESS, REJECTED, SKIPPED, INFO).
        message: Human-readable detail message.
        csv_path: Optional custom path for activity_log.csv.
        print_console: Whether to also print a formatted line to console.
    """
    path = init_activity_log(csv_path)
    now_str = datetime.now().isoformat(timespec="seconds")
    cleaned_email = normalize_email(email)

    row = {
        "timestamp": now_str,
        "event": event.strip().upper(),
        "email": cleaned_email,
        "status": status.strip().upper(),
        "message": message.strip(),
    }

    with open(path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ACTIVITY_LOG_FIELDS)
        writer.writerow(row)

    if print_console:
        email_display = f"[{cleaned_email}] " if cleaned_email else ""
        print(f"[{now_str}] [{event.upper()}] {email_display}{status.upper()}: {message}")
