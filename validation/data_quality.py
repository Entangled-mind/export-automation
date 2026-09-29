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


def _is_generic_company_domain(domain: str) -> bool:
    """Return True for obvious placeholder or generic business-brand domains."""
    if not domain:
        return False

    clean = domain.strip().lower().replace("www.", "")
    clean = clean.split("/", 1)[0].split(":", 1)[0]
    clean = clean.rstrip(".")

    if not clean or "." not in clean:
        return False

    root_label = clean.split(".", 1)[0]
    generic_labels = {
        "company",
        "companies",
        "business",
        "businesses",
        "group",
        "groups",
        "trading",
        "trade",
        "commerce",
        "enterprise",
        "enterprises",
        "industries",
        "industry",
        "solutions",
        "services",
        "partners",
        "consulting",
        "logistics",
        "global",
        "international",
        "holdings",
        "suppliers",
        "marketing",
        "technology",
        "resources",
    }

    if root_label in generic_labels:
        return True

    # Also reject domains like company.com or business.com even when they have a valid TLD.
    if root_label in {"company", "business"}:
        return True

    return False


def _company_domain_looks_verified(email: str, website: str) -> bool:
    """Return True only for business-like domains that match a real company presence."""
    if not email or not website:
        return False

    email_lower = email.strip().lower()
    website_lower = website.strip().lower()

    if "@" not in email_lower:
        return False

    email_domain = email_lower.split("@", 1)[1]
    if not email_domain:
        return False

    # Reject free-email and generic providers used for personal inboxes rather than business domains.
    generic_domains = {
        "gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "icloud.com", "protonmail.com", "aol.com", "mail.com", "gmx.com",
        "ymail.com", "live.com", "msn.com", "zoho.com"
    }
    if email_domain in generic_domains:
        return False

    # Reject obvious placeholder or example domains.
    if any(token in email_domain for token in ("example.", "test.", "sample.", "domain.", "placeholder.")):
        return False

    # Require the website to look like a real company domain, not a generic placeholder or fake TLD.
    parsed = website_lower.strip("/")
    parsed = parsed.replace("http://", "").replace("https://", "")
    if parsed.startswith("www."):
        parsed = parsed[4:]
    if any(parsed.endswith(suffix) for suffix in (".example", ".test", ".local", ".invalid")):
        return False

    # Reject clearly non-company URLs (single-word placeholder domains without business identifiers)
    root = parsed.split("/", 1)[0].split(":", 1)[0]
    if root.count(".") < 1:
        return False

    if _is_generic_company_domain(root):
        return False

    # Require the website domain and email domain to be consistent with real-company verification.
    website_domain = root.lower().split(".")
    if len(website_domain) >= 2:
        website_root = ".".join(website_domain[-2:])
        if website_root == email_domain:
            return True
        if email_domain.endswith("." + website_root):
            return True

    return False


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
    7. Real-company verification required for business acceptance -> REJECTED
    8. Fully compliant, verified lead -> VALID

    Args:
        lead: Raw or normalized buyer dictionary.
        existing_buyers: List of already cataloged buyer dictionaries.

    Returns:
        Tuple of (status: str, reason: str).
    """
    raw_email = (lead.get("email") or "").strip()
    norm = normalize_buyer(lead)
    email = norm.get("email", "")
    company = norm.get("company_name", "")
    website = norm.get("website", "")
    country = norm.get("country", "")
    source = norm.get("source_platform", "")

    # 1. Missing Email Check
    if not raw_email:
        return STATUS_REJECTED, "Missing email address."

    # 2. Placeholder / Test Email Check
    candidate_email = email or raw_email
    if is_placeholder_email(candidate_email):
        return STATUS_REJECTED, f"Placeholder or test email rejected: '{candidate_email}'."

    # 3. Email Syntax Validation
    if not is_valid_email(candidate_email):
        return STATUS_INVALID_EMAIL, f"Invalid email format: '{candidate_email}'."

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

    # 7. Real-company verification gate
    if not _company_domain_looks_verified(email, website):
        return STATUS_REJECTED, (
            "Real-company verification required: free-email or non-business domains are rejected "
            "before a lead can be accepted as a verified company contact."
        )

    # 8. Passed all quality criteria
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
