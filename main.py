"""Main entry point for EXPORT Automation System (Phase 2).

Orchestrates the complete Phase 2 pipeline:
1. Lead Discovery (Singing Bowls search adapters & directory parsing)
2. Normalization & Sanitization
3. Syntactic Email Validation
4. Duplicate Prevention (Discovery & Prior Sent History)
5. Master Buyer Cataloging (data/buyers.csv)
6. AI Classification (Google Gemini / Heuristic: B2B vs B2C)
7. Contact Segregation (data/business_buyers.csv & data/individual_buyers.csv)
8. Activity Auditing & Dynamic Performance Reporting
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from classification.classifier import classify_buyer
import config
from discovery.search_adapter import discover_buyers
from extraction.data_extractor import (
    add_buyer,
    add_classified_buyer,
    buyer_email_exists,
    init_buyers_csv,
    normalize_buyer,
)
from logging_module.activity_logger import (
    init_activity_log,
    init_sent_log,
    is_sent_successfully,
    log_activity,
    log_sent_entry,
)
from validation.email_validator import is_valid_email


def seed_demo_sent_log() -> None:
    """Seed a sample SUCCESS entry in sent_log.csv to verify outreach history checks."""
    demo_sent_email = "sarah@wellness-singingbowls.com"
    if not is_sent_successfully(demo_sent_email):
        log_sent_entry(demo_sent_email, "SUCCESS")


def run_pipeline() -> None:
    """Execute the end-to-end Phase 2 automation pipeline."""
    print("=" * 65)
    print("EXPORT Automation System - Phase 2 (Discovery & AI Pipeline)")
    print(f"Target Product : {config.SEARCH_KEYWORD}")
    print(f"Data Directory : {config.DATA_DIR}")
    engine_label = "Gemini AI" if config.GEMINI_API_KEY else "Heuristic Rule Engine (Offline/Zero-Key)"
    print(f"Classify Engine: {engine_label}")
    print("=" * 65)

    # Initialize CSV storage files
    init_buyers_csv()
    init_sent_log()
    init_activity_log()
    seed_demo_sent_log()

    log_activity(
        event="SYSTEM_INIT",
        email="",
        status="INFO",
        message="Initialized CSV databases (buyers, sent_log, activity_log, business/individual CSVs).",
    )

    # --------------------------------------------------------------------------
    # STEP 1: BUYER DISCOVERY
    # --------------------------------------------------------------------------
    print("\n[Step 1] Discovering potential Singing Bowls buyer leads...")
    raw_leads = discover_buyers(query=config.SEARCH_KEYWORD, limit=10, use_demo=True)
    print(f"-> Discovered {len(raw_leads)} prospective raw leads from search/directory adapters.\n")

    # Metrics counters
    total_leads = len(raw_leads)
    valid_emails = 0
    invalid_emails = 0
    new_buyers_added = 0
    duplicate_buyers_skipped = 0
    previously_sent_skipped = 0
    business_count = 0
    individual_count = 0

    print("--- Processing & Classifying Leads ---")

    for raw in raw_leads:
        raw_email = raw.get("email", "")

        # ----------------------------------------------------------------------
        # STEP 2: NORMALIZATION
        # ----------------------------------------------------------------------
        normalized = normalize_buyer(raw)
        email = normalized["email"]

        # ----------------------------------------------------------------------
        # STEP 3: EMAIL SYNTAX VALIDATION
        # ----------------------------------------------------------------------
        if not is_valid_email(email):
            invalid_emails += 1
            log_activity(
                event="EMAIL_VALIDATION",
                email=raw_email,
                status="REJECTED",
                message=f"Invalid email syntax: '{raw_email}'",
            )
            continue

        valid_emails += 1

        # ----------------------------------------------------------------------
        # STEP 4: DUPLICATE OUTREACH CHECK (sent_log.csv)
        # ----------------------------------------------------------------------
        if is_sent_successfully(email):
            previously_sent_skipped += 1
            log_activity(
                event="OUTREACH_CHECK",
                email=email,
                status="SKIPPED",
                message=f"Email '{email}' has prior SUCCESS in sent_log.csv. Outreach skipped.",
            )
            continue

        # ----------------------------------------------------------------------
        # STEP 5: DUPLICATE DISCOVERY CHECK (buyers.csv)
        # ----------------------------------------------------------------------
        is_already_in_master = buyer_email_exists(email)
        if is_already_in_master:
            duplicate_buyers_skipped += 1
            log_activity(
                event="DUPLICATE_CHECK",
                email=email,
                status="SKIPPED",
                message=f"Duplicate lead '{email}' already cataloged in buyers.csv.",
            )
            continue

        # Add unique lead to master buyers.csv
        success, msg = add_buyer(normalized)
        if success:
            new_buyers_added += 1
            log_activity(
                event="BUYER_CATALOGED",
                email=email,
                status="SUCCESS",
                message=f"Saved to master catalog: {normalized['buyer_name']} ({normalized['company_name']})",
            )

        # ----------------------------------------------------------------------
        # STEP 6: AI CLASSIFICATION (B2B vs B2C)
        # ----------------------------------------------------------------------
        category, reason, confidence = classify_buyer(normalized)

        if category == "BUSINESS":
            business_count += 1
        else:
            individual_count += 1

        log_activity(
            event="AI_CLASSIFICATION",
            email=email,
            status=category,
            message=f"{reason} (confidence: {confidence:.2f})",
        )

        # ----------------------------------------------------------------------
        # STEP 7: CONTACT SEGREGATION (business_buyers.csv vs individual_buyers.csv)
        # ----------------------------------------------------------------------
        add_classified_buyer(normalized, category, reason)

    # --------------------------------------------------------------------------
    # STEP 8: SUMMARY REPORT
    # --------------------------------------------------------------------------
    print("\n" + "=" * 55)
    print("EXPORT AUTOMATION SYSTEM - PHASE 2 SUMMARY")
    print("=" * 55)
    print(f"Raw leads discovered         : {total_leads}")
    print(f"Valid emails verified        : {valid_emails}")
    print(f"Invalid emails rejected      : {invalid_emails}")
    print(f"New buyers added to catalog  : {new_buyers_added}")
    print(f"Duplicate leads skipped      : {duplicate_buyers_skipped}")
    print(f"Prior sent emails skipped    : {previously_sent_skipped}")
    print("-" * 55)
    print(f"Classified as BUSINESS (B2B) : {business_count} -> data/business_buyers.csv")
    print(f"Classified as INDIVIDUAL(B2C): {individual_count} -> data/individual_buyers.csv")
    print("=" * 55)
    print("Phase 2 pipeline completed successfully.\n")


if __name__ == "__main__":
    run_pipeline()
