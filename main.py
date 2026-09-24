"""Main entry point for EXPORT Automation System (Phase 2: Lead Discovery + Data Quality).

Orchestrates the Phase 2 discovery and data-quality pipeline:
1. Lead Discovery (search/ package: Google Search, Business Directories, Website Extraction)
2. Data Extraction & Normalization
3. Email Syntax Validation & Placeholder Filtering
4. Data Quality & Metadata Hygiene Checks (VALID, INCOMPLETE, INVALID_EMAIL, DUPLICATE, REJECTED)
5. Duplicate Prevention (Cross-referencing buyers.csv)
6. Master Lead Cataloging (data/buyers.csv)
7. Activity Auditing (data/activity_log.csv)
8. Discovery Statistics & Reporting
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from extraction.data_extractor import (
    add_buyer,
    init_buyers_csv,
    normalize_buyer,
    read_all_buyers,
)
from logging_module.activity_logger import (
    init_activity_log,
    init_sent_log,
    log_activity,
)
from search import discover_all_leads
from validation.data_quality import (
    STATUS_DUPLICATE,
    STATUS_INCOMPLETE,
    STATUS_INVALID_EMAIL,
    STATUS_REJECTED,
    STATUS_VALID,
    DiscoveryStatistics,
    assess_lead_quality,
)


def run_pipeline() -> DiscoveryStatistics:
    """Execute the Phase 2 Lead Discovery and Data Quality pipeline.

    Returns:
        DiscoveryStatistics object containing aggregated execution metrics.
    """
    stats = DiscoveryStatistics()

    print("=" * 65)
    print("EXPORT AUTOMATION SYSTEM -- PHASE 2 (LEAD DISCOVERY + DATA QUALITY)")
    print(f"Target Product : {config.SEARCH_KEYWORD}")
    print(f"Execution Mode : {'TEST_MODE (Offline Mock Fixtures)' if config.TEST_MODE else 'LIVE MODE'}")
    print(f"Data Directory : {config.DATA_DIR}")
    print("=" * 65)

    # Initialize CSV storage files
    init_buyers_csv()
    init_sent_log()
    init_activity_log()

    log_activity(
        event="PIPELINE_INIT",
        email="",
        status="INFO",
        message=f"Initialized Phase 2 discovery pipeline. TEST_MODE={config.TEST_MODE}.",
    )

    # --------------------------------------------------------------------------
    # STEP 1: LEAD DISCOVERY
    # --------------------------------------------------------------------------
    print("\n[Step 1] Discovering buyer leads across modular search adapters...")
    raw_leads = discover_all_leads(
        query=config.SEARCH_KEYWORD,
        limit=15,
        test_mode=config.TEST_MODE,
    )
    print(f"-> Discovered {len(raw_leads)} raw results from Google, Directories, and Websites.\n")

    # Read existing buyers to check for duplicates
    existing_buyers = read_all_buyers()

    print("--- Processing Leads & Assessing Data Quality ---")

    for raw in raw_leads:
        # ----------------------------------------------------------------------
        # STEP 2 & 3: EXTRACTION & NORMALIZATION
        # ----------------------------------------------------------------------
        normalized = normalize_buyer(raw)
        email = normalized.get("email", "")
        company = normalized.get("company_name", "")
        buyer_name = normalized.get("buyer_name", "")

        # ----------------------------------------------------------------------
        # STEP 4 & 5: DATA QUALITY ASSESSMENT & DEDUPLICATION
        # ----------------------------------------------------------------------
        quality_status, reason = assess_lead_quality(normalized, existing_buyers)

        if quality_status in (STATUS_VALID, STATUS_INCOMPLETE):
            # Lead has valid email and is not a duplicate -> Save to database
            success, msg = add_buyer(normalized)

            if success:
                # Update local cache so subsequent leads in this batch are checked against it
                existing_buyers.append(normalized)
                stats.record_lead(quality_status, is_newly_saved=True)
                log_activity(
                    event="LEAD_CATALOGED",
                    email=email,
                    status=quality_status,
                    message=f"Saved lead: {buyer_name or 'N/A'} ({company or 'Individual'}) - {reason}",
                )
                print(f"  [SAVED] {email:<32} | Status: {quality_status:<10} | {company}")
            else:
                stats.record_lead(STATUS_DUPLICATE, is_newly_saved=False)
                log_activity(
                    event="DUPLICATE_SUPPRESSED",
                    email=email,
                    status="DUPLICATE",
                    message=msg,
                )
                print(f"  [DUP]   {email:<32} | Status: DUPLICATE  | {msg}")

        elif quality_status == STATUS_DUPLICATE:
            stats.record_lead(STATUS_DUPLICATE, is_newly_saved=False)
            log_activity(
                event="DUPLICATE_CHECK",
                email=email,
                status="DUPLICATE",
                message=reason,
            )
            print(f"  [DUP]   {email:<32} | Status: DUPLICATE  | {reason}")

        elif quality_status == STATUS_INVALID_EMAIL:
            stats.record_lead(STATUS_INVALID_EMAIL, is_newly_saved=False)
            log_activity(
                event="EMAIL_VALIDATION",
                email=email,
                status="INVALID_EMAIL",
                message=reason,
            )
            print(f"  [REJ]   {email:<32} | Status: INVALID_EMAIL | {reason}")

        elif quality_status == STATUS_REJECTED:
            stats.record_lead(STATUS_REJECTED, is_newly_saved=False)
            log_activity(
                event="DATA_QUALITY",
                email=email,
                status="REJECTED",
                message=reason,
            )
            print(f"  [REJ]   {email:<32} | Status: REJECTED   | {reason}")

    # --------------------------------------------------------------------------
    # STEP 6: SUMMARY REPORT
    # --------------------------------------------------------------------------
    print()
    stats.print_summary()
    return stats


if __name__ == "__main__":
    run_pipeline()
