"""Email validation and duplicate checking module for EXPORT Automation System.

Provides syntax and structural validation for buyer email addresses, along with
reusable duplicate detection against buyers.csv and sent_log.csv.

LIMITATION NOTICE:
This Phase 1 validator strictly performs local syntax and format validation.
It does NOT connect to external networks or verify SMTP server availability,
and cannot guarantee that an email mailbox actually exists or is deliverable.
"""

import re
from pathlib import Path
from typing import Optional, Tuple

from extraction.data_extractor import buyer_email_exists, normalize_email
from logging_module.activity_logger import is_sent_successfully

# Regular expression for standard email syntax validation
# Requires local-part @ domain-name . domain-extension (min 2 chars)
EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9]+([.-][a-zA-Z0-9]+)*\.[a-zA-Z]{2,}$"
)

# Known dummy placeholders that should be explicitly rejected
KNOWN_PLACEHOLDERS = {
    "test",
    "test@test",
    "example@example",
    "invalid-email",
    "sample@sample",
    "email@example.com",
}


def is_valid_email(email: Optional[str]) -> bool:
    """Validate whether an email address matches standard syntactic rules.

    Checks performed:
    1. Email exists and is a string.
    2. Email does not contain any spaces or control characters.
    3. Email contains exactly one '@' separator.
    4. Local part (before '@') and domain part (after '@') are non-empty.
    5. Domain contains at least one dot separating subdomains/TLD with valid characters.
    6. Email is not an obvious placeholder string (e.g. 'test', 'example@example').

    Args:
        email: Email address string to test.

    Returns:
        True if email has valid syntax, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False

    # Check for whitespace anywhere inside the string
    if any(ch.isspace() for ch in email):
        return False

    cleaned = email.strip().lower()

    # Reject known obvious placeholders
    if cleaned in KNOWN_PLACEHOLDERS:
        return False

    # Check basic regex structure
    if not EMAIL_PATTERN.match(cleaned):
        return False

    # Ensure local and domain parts are sensible
    parts = cleaned.split("@")
    if len(parts) != 2:
        return False

    local_part, domain_part = parts
    if not local_part or not domain_part:
        return False

    # Domain must contain at least one dot and cannot start or end with a dot or hyphen
    domain_segments = domain_part.split(".")
    if len(domain_segments) < 2:
        return False

    for segment in domain_segments:
        if not segment or segment.startswith("-") or segment.endswith("-"):
            return False

    return True


def is_duplicate_buyer(email: str, buyers_csv_path: Optional[Path] = None) -> bool:
    """Check if an email already exists in the buyers database.

    Args:
        email: Email address to verify.
        buyers_csv_path: Optional custom path to buyers.csv.

    Returns:
        True if already in buyers.csv, False otherwise.
    """
    return buyer_email_exists(email, buyers_csv_path)


def is_duplicate_outreach(email: str, sent_log_path: Optional[Path] = None) -> bool:
    """Check if an email has already been sent to successfully.

    Args:
        email: Email address to verify.
        sent_log_path: Optional custom path to sent_log.csv.

    Returns:
        True if a SUCCESS record exists in sent_log.csv, False otherwise.
    """
    return is_sent_successfully(email, sent_log_path)


def check_outreach_eligibility(
    email: str,
    buyers_csv_path: Optional[Path] = None,
    sent_log_path: Optional[Path] = None,
) -> Tuple[str, str]:
    """Perform full duplicate & validation screening for buyer outreach.

    Decision flow:
    1. If email has invalid syntax -> REJECTED_INVALID
    2. If email was already sent outreach successfully -> SKIPPED_PREVIOUSLY_SENT
    3. If email is already present in buyers.csv -> SKIPPED_DUPLICATE_BUYER
    4. Otherwise -> ELIGIBLE

    Args:
        email: Email address to evaluate.
        buyers_csv_path: Optional path to buyers.csv.
        sent_log_path: Optional path to sent_log.csv.

    Returns:
        Tuple of (status_code: str, reason_message: str).
    """
    cleaned = normalize_email(email)

    if not is_valid_email(cleaned):
        return "REJECTED_INVALID", f"Invalid email format: '{email}'"

    if is_duplicate_outreach(cleaned, sent_log_path):
        return "SKIPPED_PREVIOUSLY_SENT", f"Outreach already completed successfully for '{cleaned}'"

    if is_duplicate_buyer(cleaned, buyers_csv_path):
        return "SKIPPED_DUPLICATE_BUYER", f"Buyer already exists in database: '{cleaned}'"

    return "ELIGIBLE", f"Email '{cleaned}' is valid and eligible for future outreach"
