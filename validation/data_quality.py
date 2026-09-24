"""Data Quality Assessment module for EXPORT Automation System (Phase 2).

Provides comprehensive data hygiene, quality classification, and discovery
statistics tracking for buyer leads:
- Statuses: VALID, INCOMPLETE, INVALID_EMAIL, DUPLICATE, REJECTED
- Checks for missing fields, placeholder emails, syntax errors, and duplicates
- Discovery statistics aggregator
"""

from typing import Dict, List, Optional, Tuple
import config
from extraction.data_extractor import (
    buyer_company_and_website_exists,
    normalize_buyer,
    normalize_email,
)
from validation.email_validator import (
    KNOWN_PLACEHOLDERS,
    is_placeholder_email,
    is_valid_email,
)

# Quality Status Constants
STATUS_VALID = config.STATUS_VALID
STATUS_INCOMPLETE = config.STATUS_INCOMPLETE
STATUS_INVALID_EMAIL = config.STATUS_INVALID_EMAIL
STATUS_DUPLICATE = config.STATUS_DUPLICATE
STATUS_REJECTED = config.STATUS_REJECTED


def assess_lead_quality(
    lead: Dict[str, str],
    existing_buyers: Optional[List[Dict[str, str]]] = None,
) -> Tuple[str, str]:
    """Evaluate data quality and determine admission status for a prospective lead.

    Evaluates:
    1. Missing email -> REJECTED
    2. Placeholder / dummy email -> REJECTED
    3. Invalid email syntax (spaces, malformed domain) -> INVALID_EMAIL
    4. Duplicate email in database -> DUPLICATE
    5. Duplicate company + website in database -> DUPLICATE
    6. Missing metadata (company, website, country, or source) -> INCOMPLETE
    7. Fully compliant, verified lead -> VALID

    Args:
        lead: Raw or normalized buyer dictionary.
        existing_buyers: List of already cataloged buyer dictionaries.

    Returns:
        Tuple of (status: str, reason: str).
    """
    norm = normalize_buyer(lead)
    email = norm.get("email", "")
    company = norm.get("company_name", "")
    website = norm.get("website", "")
    country = norm.get("country", "")
    source = norm.get("source_platform", "")

    # 1. Missing Email Check
    if not email:
        return STATUS_REJECTED, "Missing email address."

    # 2. Placeholder / Test Email Check
    if is_placeholder_email(email):
        return STATUS_REJECTED, f"Placeholder or test email rejected: '{email}'."

    # 3. Email Syntax Validation
    if not is_valid_email(email):
        return STATUS_INVALID_EMAIL, f"Invalid email format: '{email}'."

    # 4. Duplicate Email Detection
    if existing_buyers is not None:
        for b in existing_buyers:
            if normalize_email(b.get("email")) == email:
                return STATUS_DUPLICATE, f"Duplicate lead: email '{email}' already cataloged."

    # 5. Duplicate Company + Website Detection
    if company and website and existing_buyers is not None:
        if buyer_company_and_website_exists(company, website, existing_buyers):
            return STATUS_DUPLICATE, f"Duplicate entity: company '{company}' and website '{website}' already cataloged."

    # 6. Incomplete Metadata Check
    missing = []
    if not company:
        missing.append("company_name")
    if not website:
        missing.append("website")
    if not country:
        missing.append("country")
    if not source:
        missing.append("source_platform")

    if missing:
        missing_str = ", ".join(missing)
        return STATUS_INCOMPLETE, f"Valid email, but missing metadata: [{missing_str}]."

    # 7. Passed all quality criteria
    return STATUS_VALID, "Lead passed all data-quality checks."


class DiscoveryStatistics:
    """Tracks and aggregates lead discovery and data-quality metrics."""

    def __init__(self) -> None:
        self.raw_results: int = 0
        self.valid_leads: int = 0
        self.incomplete_leads: int = 0
        self.invalid_leads: int = 0
        self.duplicates: int = 0
        self.new_leads: int = 0

    def record_lead(self, status: str, is_newly_saved: bool = False) -> None:
        """Update metrics based on lead assessment status."""
        self.raw_results += 1
        if status == STATUS_VALID:
            self.valid_leads += 1
        elif status == STATUS_INCOMPLETE:
            self.incomplete_leads += 1
        elif status == STATUS_INVALID_EMAIL:
            self.invalid_leads += 1
        elif status == STATUS_DUPLICATE:
            self.duplicates += 1
        elif status == STATUS_REJECTED:
            self.invalid_leads += 1

        if is_newly_saved:
            self.new_leads += 1

    def to_dict(self) -> Dict[str, int]:
        """Return metrics as a dictionary."""
        return {
            "raw_results": self.raw_results,
            "valid_leads": self.valid_leads,
            "incomplete_leads": self.incomplete_leads,
            "invalid_leads": self.invalid_leads,
            "duplicates": self.duplicates,
            "new_leads": self.new_leads,
        }

    def print_summary(self) -> None:
        """Display a formatted discovery metrics report in console."""
        print("=" * 65)
        print("PHASE 2: LEAD DISCOVERY & DATA QUALITY REPORT")
        print("=" * 65)
        print(f"Total Raw Results Discovered : {self.raw_results}")
        print(f"Valid Complete Leads         : {self.valid_leads}")
        print(f"Incomplete Leads (Missing Info): {self.incomplete_leads}")
        print(f"Invalid / Rejected Leads     : {self.invalid_leads}")
        print(f"Duplicate Leads (Suppressed) : {self.duplicates}")
        print(f"New Leads Saved to Database  : {self.new_leads}")
        print("=" * 65)
