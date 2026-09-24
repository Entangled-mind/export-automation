"""Main entry point for EXPORT Automation System (Phase 3: AI Lead Classification).

Orchestrates the end-to-end export automation pipeline:
1. Lead Discovery (search/ package: Google Search, B2B Directories, Website Crawling)
2. Data Extraction & Normalization
3. Email Syntax Validation & Data Quality Checks (VALID, INCOMPLETE, INVALID_EMAIL, DUPLICATE, REJECTED)
4. Duplicate Prevention & Master Cataloging (data/buyers.csv)
5. AI Lead Classification & Priority Tiering (classification/ package: Gemini AI / Mock AI)
   - Evaluates fit for Himalayan Singing Bowls export products
   - Assigns Priority Tiers (Tier 1 High, Tier 2 Medium, Tier 3 Low, Irrelevant)
   - Computes Intent Score (0 - 100) & recommends tailored outreach angle
6. Segregated Storage Management (data/business_buyers.csv vs data/individual_buyers.csv)
7. Audit Logging (data/activity_log.csv)
8. Discovery & Classification Reporting
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from classification import (
    CATEGORY_BUSINESS,
    CATEGORY_INDIVIDUAL,
    CATEGORY_IRRELEVANT,
    TIER_1,
    TIER_2,
    TIER_3,
    TIER_IRRELEVANT,
    ClassificationStatistics,
    LeadClassification,
    classify_lead,
)
from extraction.data_extractor import (
    add_buyer,
    add_classified_buyer,
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


def run_pipeline() -> Tuple[DiscoveryStatistics, ClassificationStatistics]:
    """Execute the Phase 3 Discovery and AI Classification pipeline.

    Returns:
        Tuple of (DiscoveryStatistics, ClassificationStatistics).
    """
    disc_stats = DiscoveryStatistics()
    class_stats = ClassificationStatistics()

    print("=" * 68)
    print("EXPORT AUTOMATION SYSTEM -- PHASE 3 (AI LEAD CLASSIFICATION)")
    print(f"Target Product : {config.SEARCH_KEYWORD}")
    print(f"Execution Mode : {'TEST_MODE (Offline Mock AI)' if config.TEST_MODE else 'LIVE MODE'}")
    print(f"Gemini Model   : {config.GEMINI_MODEL}")
    print(f"Data Directory : {config.DATA_DIR}")
    print("=" * 68)

    # Initialize CSV storage files
    init_buyers_csv()
    init_sent_log()
    init_activity_log()

    log_activity(
        event="PIPELINE_INIT",
        email="",
        status="INFO",
        message=f"Initialized Phase 3 pipeline. TEST_MODE={config.TEST_MODE}.",
    )

    # --------------------------------------------------------------------------
    # STEP 1: LEAD DISCOVERY
    # --------------------------------------------------------------------------
    print("\n[Step 1] Discovering buyer leads across search adapters...")
    raw_leads = discover_all_leads(
        query=config.SEARCH_KEYWORD,
        limit=15,
        test_mode=config.TEST_MODE,
    )
    print(f"-> Discovered {len(raw_leads)} raw results from Google, Directories, and Websites.\n")

    # Read existing buyers to check for duplicates
    existing_buyers = read_all_buyers()
    newly_saved_leads: List[Dict[str, str]] = []

    print("--- Step 2: Assessing Data Quality & Deduplication ---")

    for raw in raw_leads:
        normalized = normalize_buyer(raw)
        email = normalized.get("email", "")
        company = normalized.get("company_name", "")
        buyer_name = normalized.get("buyer_name", "")

        quality_status, reason = assess_lead_quality(normalized, existing_buyers)

        if quality_status in (STATUS_VALID, STATUS_INCOMPLETE):
            success, msg = add_buyer(normalized)

            if success:
                existing_buyers.append(normalized)
                newly_saved_leads.append(normalized)
                disc_stats.record_lead(quality_status, is_newly_saved=True)
                log_activity(
                    event="LEAD_CATALOGED",
                    email=email,
                    status=quality_status,
                    message=f"Saved lead: {buyer_name or 'N/A'} ({company or 'Individual'}) - {reason}",
                )
                print(f"  [SAVED] {email:<32} | Status: {quality_status:<10} | {company}")
            else:
                disc_stats.record_lead(STATUS_DUPLICATE, is_newly_saved=False)
                log_activity(
                    event="DUPLICATE_SUPPRESSED",
                    email=email,
                    status="DUPLICATE",
                    message=msg,
                )
                print(f"  [DUP]   {email:<32} | Status: DUPLICATE  | {msg}")

        elif quality_status == STATUS_DUPLICATE:
            disc_stats.record_lead(STATUS_DUPLICATE, is_newly_saved=False)
            log_activity(
                event="DUPLICATE_CHECK",
                email=email,
                status="DUPLICATE",
                message=reason,
            )
            print(f"  [DUP]   {email:<32} | Status: DUPLICATE  | {reason}")

        elif quality_status == STATUS_INVALID_EMAIL:
            disc_stats.record_lead(STATUS_INVALID_EMAIL, is_newly_saved=False)
            log_activity(
                event="EMAIL_VALIDATION",
                email=email,
                status="INVALID_EMAIL",
                message=reason,
            )
            print(f"  [REJ]   {email:<32} | Status: INVALID_EMAIL | {reason}")

        elif quality_status == STATUS_REJECTED:
            disc_stats.record_lead(STATUS_REJECTED, is_newly_saved=False)
            log_activity(
                event="DATA_QUALITY",
                email=email,
                status="REJECTED",
                message=reason,
            )
            print(f"  [REJ]   {email:<32} | Status: REJECTED   | {reason}")

    # --------------------------------------------------------------------------
    # STEP 3: AI LEAD CLASSIFICATION & PRIORITY TIERING
    # --------------------------------------------------------------------------
    print("\n--- Step 3: AI Lead Classification & Priority Tiering ---")
    
    # Classify all verified leads in the master catalog
    catalog_to_classify = existing_buyers if existing_buyers else newly_saved_leads
    classified_leads: List[Tuple[Dict[str, str], LeadClassification]] = []

    for buyer in catalog_to_classify:
        email = buyer.get("email", "")
        if not email:
            continue

        classification = classify_lead(buyer, use_ai=True, test_mode=config.TEST_MODE)
        class_stats.record(classification)
        classified_leads.append((buyer, classification))

        # Store in segregated storage (business vs individual) if not irrelevant
        if classification.category in (CATEGORY_BUSINESS, CATEGORY_INDIVIDUAL):
            add_classified_buyer(
                buyer_data=buyer,
                classification=classification.category,
                reasoning=classification.reasoning,
                tier=classification.tier,
                intent_score=classification.intent_score,
                outreach_angle=classification.outreach_angle,
                overwrite=True,
            )

        log_activity(
            event="LEAD_CLASSIFIED",
            email=email,
            status=classification.tier,
            message=f"{classification.category} (Score: {classification.intent_score}) | {classification.outreach_angle}",
        )

        tier_badge = (
            "[T1]" if classification.tier == TIER_1
            else "[T2]" if classification.tier == TIER_2
            else "[T3]" if classification.tier == TIER_3
            else "[--]"
        )
        print(f"  {tier_badge} {email:<32} | {classification.category:<10} | Score: {classification.intent_score:>2} | {classification.tier}")

    # --------------------------------------------------------------------------
    # STEP 4: SUMMARY & STATISTICAL REPORTS
    # --------------------------------------------------------------------------
    print()
    disc_stats.print_summary()

    print("\n" + "=" * 68)
    print("PHASE 3: AI LEAD CLASSIFICATION & TIER REPORT")
    print("=" * 68)
    print(f"Total Leads Evaluated        : {class_stats.total_evaluated}")
    print(f"B2B Wholesale / Studios      : {class_stats.business_count}")
    print(f"B2C Solo / Personal Buyers   : {class_stats.individual_count}")
    print(f"Irrelevant / Unqualified     : {class_stats.irrelevant_count}")
    print("-" * 68)
    print(f"Tier 1 (High Priority Bulk)  : {class_stats.tier_1_count}")
    print(f"Tier 2 (Medium Priority)     : {class_stats.tier_2_count}")
    print(f"Tier 3 (Low Priority Solo)   : {class_stats.tier_3_count}")
    print("-" * 68)
    print(f"AI Evaluated Leads           : {class_stats.ai_count}")
    print(f"Heuristic Evaluated Leads    : {class_stats.heuristic_count}")
    print("=" * 68)

    # Print top qualified leads sample
    tier_1_leads = [
        (b, c) for b, c in classified_leads if c.tier == TIER_1
    ][:3]
    if tier_1_leads:
        print("\nTOP QUALIFIED LEADS (TIER 1 PREVIEW):")
        for buyer, c in tier_1_leads:
            print(f" * Company : {buyer.get('company_name') or 'N/A'}")
            print(f"   Email   : {buyer.get('email')}")
            print(f"   Score   : {c.intent_score}/100 | Confidence: {c.confidence:.0%}")
            print(f"   Angle   : {c.outreach_angle}")
            print(f"   Reason  : {c.reasoning}\n")

    return disc_stats, class_stats


if __name__ == "__main__":
    run_pipeline()
