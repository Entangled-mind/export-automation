"""Data extraction, normalization, and segregated storage module for EXPORT Automation System.

Handles cleaning buyer records and managing the local CSV databases:
- data/buyers.csv (master database)
- data/business_buyers.csv (B2B wholesale / studio leads)
- data/individual_buyers.csv (B2C consumer leads)
"""

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import config

# Standard field definitions for buyer records
BUYER_FIELDS = [
    "buyer_name",
    "company_name",
    "email",
    "website",
    "country",
    "source_platform",
]

CLASSIFIED_FIELDS = [
    "buyer_name",
    "company_name",
    "email",
    "website",
    "country",
    "source_platform",
    "classification",
    "tier",
    "intent_score",
    "outreach_angle",
    "reasoning",
]


def normalize_email(email: Optional[str]) -> str:
    """Normalize an email address by trimming whitespace and converting to lowercase.

    Args:
        email: Raw email string or None.

    Returns:
        Cleaned lowercase email string, or empty string if input is invalid.
    """
    if not email or not isinstance(email, str):
        return ""
    return email.strip().lower()


def normalize_buyer(raw_data: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Normalize a raw buyer dictionary into a standard, clean buyer record.

    Trims leading/trailing whitespace on all text fields, standardizes the email,
    and ensures missing fields default to empty strings without crashing.

    Args:
        raw_data: Dictionary containing raw buyer attributes.

    Returns:
        Standardized dictionary with keys: buyer_name, company_name, email,
        website, country, and source_platform.
    """
    if not isinstance(raw_data, dict):
        raw_data = {}

    def clean_field(val: Optional[str]) -> str:
        if val is None:
            return ""
        if not isinstance(val, str):
            val = str(val)
        return val.strip()

    normalized = {
        "buyer_name": clean_field(raw_data.get("buyer_name")),
        "company_name": clean_field(raw_data.get("company_name")),
        "email": normalize_email(raw_data.get("email")),
        "website": clean_field(raw_data.get("website")),
        "country": clean_field(raw_data.get("country")),
        "source_platform": clean_field(raw_data.get("source_platform")),
    }
    return normalized


def init_buyers_csv(csv_path: Optional[Path] = None) -> Path:
    """Initialize buyers.csv file with headers if it does not already exist.

    Args:
        csv_path: Optional custom path for buyers.csv. Defaults to config.BUYERS_CSV.

    Returns:
        Path to the initialized buyers.csv file.
    """
    path = Path(csv_path) if csv_path else config.BUYERS_CSV
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists() or path.stat().st_size == 0:
        with open(path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=BUYER_FIELDS)
            writer.writeheader()
    return path


def read_all_buyers(csv_path: Optional[Path] = None) -> List[Dict[str, str]]:
    """Read all buyer records from buyers.csv.

    Args:
        csv_path: Optional custom path for buyers.csv.

    Returns:
        List of dictionaries containing normalized buyer records.
    """
    path = init_buyers_csv(csv_path)
    buyers: List[Dict[str, str]] = []

    with open(path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            buyers.append(normalize_buyer(row))
    return buyers


def buyer_email_exists(email: str, csv_path: Optional[Path] = None) -> bool:
    """Check if an email address already exists in buyers.csv (case-insensitive).

    Args:
        email: Email address to search for.
        csv_path: Optional custom path for buyers.csv.

    Returns:
        True if the email exists, False otherwise.
    """
    target = normalize_email(email)
    if not target:
        return False

    all_buyers = read_all_buyers(csv_path)
    for buyer in all_buyers:
        if normalize_email(buyer.get("email")) == target:
            return True
    return False


def buyer_company_and_website_exists(
    company: str,
    website: str,
    existing_buyers: Optional[List[Dict[str, str]]] = None,
    csv_path: Optional[Path] = None,
) -> bool:
    """Check if a buyer with the same company name and website already exists.

    Args:
        company: Company name to check.
        website: Website URL to check.
        existing_buyers: Optional pre-loaded list of buyer dictionaries.
        csv_path: Optional custom path for buyers.csv.

    Returns:
        True if both company and website match an existing record, False otherwise.
    """
    clean_company = (company or "").strip().lower()
    clean_website = (website or "").strip().lower().rstrip("/")
    if not clean_company or not clean_website:
        return False

    buyers = existing_buyers if existing_buyers is not None else read_all_buyers(csv_path)
    for b in buyers:
        b_company = (b.get("company_name") or "").strip().lower()
        b_website = (b.get("website") or "").strip().lower().rstrip("/")
        if b_company and b_website and b_company == clean_company and b_website == clean_website:
            return True
    return False



def add_buyer(
    buyer_data: Dict[str, str], csv_path: Optional[Path] = None
) -> Tuple[bool, str]:
    """Add a new buyer record to buyers.csv if the email is not a duplicate.

    Args:
        buyer_data: Raw or normalized dictionary of buyer attributes.
        csv_path: Optional custom path for buyers.csv.

    Returns:
        A tuple of (success: bool, message: str).
    """
    normalized = normalize_buyer(buyer_data)
    email = normalized["email"]

    if not email:
        return False, "Cannot add buyer: email is empty or invalid"

    if buyer_email_exists(email, csv_path):
        return False, f"Duplicate skipped: '{email}' already exists in buyers database"

    path = init_buyers_csv(csv_path)
    with open(path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BUYER_FIELDS)
        writer.writerow(normalized)

    # Synchronize with SQLite database in default mode
    if csv_path is None:
        try:
            from database.repository import upsert_buyer
            upsert_buyer(normalized)
        except Exception:
            pass

    return True, f"Buyer '{normalized['buyer_name']}' ({email}) added successfully"


# ==============================================================================
# PHASE 2: SEGREGATED CLASSIFIED CSV STORAGE (B2B vs B2C)
# ==============================================================================

def init_classified_csv(csv_path: Path) -> Path:
    """Initialize or migrate a classified CSV with headers and modern schema.

    Args:
        csv_path: Path to target classified CSV file.

    Returns:
        Path to the initialized CSV.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CLASSIFIED_FIELDS)
            writer.writeheader()
        return csv_path

    # If file exists, verify and migrate if headers do not match modern CLASSIFIED_FIELDS
    with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, [])

    if header and header != CLASSIFIED_FIELDS:
        with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
            dict_reader = csv.DictReader(f)
            existing_rows = list(dict_reader)
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CLASSIFIED_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in existing_rows:
                row.setdefault("tier", "")
                row.setdefault("intent_score", "")
                row.setdefault("outreach_angle", "")
                writer.writerow(row)

    return csv_path


def add_classified_buyer(
    buyer_data: Dict[str, str],
    classification: str,
    reasoning: str = "",
    custom_path: Optional[Path] = None,
    tier: str = "",
    intent_score: int = 0,
    outreach_angle: str = "",
    overwrite: bool = False,
) -> Tuple[bool, str]:
    """Store a classified buyer record into business_buyers.csv or individual_buyers.csv.

    Args:
        buyer_data: Normalized buyer dictionary.
        classification: 'BUSINESS' or 'INDIVIDUAL'.
        reasoning: Explanation for classification.
        custom_path: Optional custom file path for testing.
        tier: Priority tier (e.g. 'Tier 1 - High Priority').
        intent_score: Purchase intent score (0-100).
        outreach_angle: Personalized product pitch angle.
        overwrite: If True, updates existing record with new classification data.

    Returns:
        Tuple of (success: bool, message: str).
    """
    normalized = normalize_buyer(buyer_data)
    email = normalized["email"]
    if not email:
        return False, "Email cannot be empty"

    category = classification.strip().upper()
    if custom_path:
        target_path = Path(custom_path)
    else:
        target_path = (
            config.BUSINESS_BUYERS_CSV
            if category == "BUSINESS"
            else config.INDIVIDUAL_BUYERS_CSV
        )

    init_classified_csv(target_path)

    record = dict(normalized)
    record["classification"] = category
    record["tier"] = tier.strip()
    record["intent_score"] = str(intent_score) if intent_score else ""
    record["outreach_angle"] = outreach_angle.strip()
    record["reasoning"] = reasoning.strip()

    # Check for existing record in target file
    existing_rows = []
    found_idx = -1
    with open(target_path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if normalize_email(row.get("email")) == email:
                found_idx = idx
                if not overwrite:
                    return False, f"Buyer '{email}' already exists in {target_path.name}"
            existing_rows.append(dict(row))

    if found_idx >= 0 and overwrite:
        existing_rows[found_idx] = record
        with open(target_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CLASSIFIED_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(existing_rows)
        return True, f"Updated '{email}' in {target_path.name}"

    with open(target_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CLASSIFIED_FIELDS, extrasaction="ignore")
        writer.writerow(record)

    # Synchronize with SQLite database in default mode
    if custom_path is None:
        try:
            from database.repository import save_classification
            score_val = int(intent_score) if intent_score else 0
            save_classification(
                email=email,
                category=category,
                tier=tier,
                intent_score=score_val,
                confidence=0.90,
                outreach_angle=outreach_angle,
                reasoning=reasoning,
                source="Pipeline",
            )
        except Exception:
            pass

    return True, f"Saved '{email}' to {target_path.name}"


def read_classified_buyers(
    category: str = "BUSINESS", custom_path: Optional[Path] = None
) -> List[Dict[str, str]]:
    """Read all records from a segregated buyer file.

    Args:
        category: 'BUSINESS' or 'INDIVIDUAL'.
        custom_path: Optional custom path.

    Returns:
        List of classified buyer dictionaries.
    """
    target_path = custom_path or (
        config.BUSINESS_BUYERS_CSV
        if category.upper() == "BUSINESS"
        else config.INDIVIDUAL_BUYERS_CSV
    )
    init_classified_csv(target_path)

    records: List[Dict[str, str]] = []
    with open(target_path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(dict(row))
    return records
