"""Main entry point for EXPORT Automation System (Phase 7: Production Polish & CLI Orchestration).

Orchestrates the complete 6-stage export automation pipeline:
1. Enterprise SQLite Database Initialization & Automated CSV Migration (database/ package)
2. Lead Discovery (search/ package: Google Search, B2B Directories, Website Crawling)
3. Data Extraction, Normalization & Quality Assessment (VALID, INCOMPLETE, INVALID_EMAIL, DUPLICATE, REJECTED)
4. AI Lead Classification & Priority Tiering (classification/ package: Gemini AI / Heuristic Fallback)
   - Evaluates buyer fit for Himalayan Singing Bowls export products
   - Assigns Priority Tiers (Tier 1 High, Tier 2 Medium, Tier 3 Low, Irrelevant)
   - Computes Intent Score (0 - 100) & recommends tailored outreach angle
5. Relational Persistence & Segregated Storage (SQLite buyers/classifications tables & CSV mirrors)
6. Automated Outreach & Email Automation (outreach/ package: Gmail SMTP / Safe Dry-Run Simulation)
   - Composes personalized Plain Text and HTML MIME emails with dynamic placeholders
   - Attaches official B2B Export Catalog Presentation PDF (assets/company_presentation.pdf)
   - Enforces duplicate outreach screening and daily sending quotas
   - Operates in safe dry-run simulation mode when TEST_MODE=True or DRY_RUN=True
7. Audit Logging & Real-time Executive Database Reporting
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
from database import (
    get_all_buyers,
    get_database_stats,
    init_database,
    migrate_csv_to_sqlite,
    record_activity,
    record_outreach,
    save_classification,
    upsert_buyer,
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
from outreach import (
    OutreachResult,
    OutreachStatistics,
    can_send_today,
    get_today_sent_count,
    send_batch_outreach,
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


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments for pipeline execution."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="EXPORT Automation System: B2B Lead Discovery, AI Qualification, and Outreach Pipeline.",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--test",
        dest="test_mode",
        action="store_true",
        default=None,
        help="Force test mode (uses mock search adapters and offline test fallbacks).",
    )
    mode_group.add_argument(
        "--live",
        dest="test_mode",
        action="store_false",
        help="Run in live production mode (queries live search engines and Gemini AI).",
    )

    dry_group = parser.add_mutually_exclusive_group()
    dry_group.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=None,
        help="Simulate email outreach dispatches without sending live SMTP messages.",
    )
    dry_group.add_argument(
        "--live-send",
        dest="dry_run",
        action="store_false",
        help="Enable live SMTP email dispatch (requires configured SMTP credentials).",
    )

    parser.add_argument(
        "--query",
        "-q",
        type=str,
        default=None,
        help="Target export product search query (e.g. 'Singing Bowls wholesale imports studio').",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=15,
        help="Maximum number of leads to fetch per discovery adapter (default: 15).",
    )
    parser.add_argument(
        "--no-discovery",
        action="store_true",
        default=False,
        help="Skip web discovery and process existing leads in the database.",
    )
    parser.add_argument(
        "--no-outreach",
        action="store_true",
        default=False,
        help="Skip the email outreach campaign dispatch step.",
    )
    parser.add_argument(
        "--tier",
        type=str,
        default="1,2",
        help="Comma-separated target tiers for outreach: '1', '2', '3', or '1,2' (default: '1,2').",
    )

    return parser.parse_args(args)


def run_pipeline(
    test_mode: Optional[bool] = None,
    dry_run: Optional[bool] = None,
    query: Optional[str] = None,
    limit: int = 15,
    skip_discovery: bool = False,
    target_tiers: Optional[List[str]] = None,
    skip_outreach: bool = False,
) -> Tuple[DiscoveryStatistics, ClassificationStatistics, OutreachStatistics, Dict[str, Any]]:
    """Execute the End-to-End Export Automation Pipeline.

    Args:
        test_mode: Override config.TEST_MODE if provided.
        dry_run: Override config.DRY_RUN if provided.
        query: Override config.SEARCH_KEYWORD if provided.
        limit: Max leads to fetch per discovery adapter.
        skip_discovery: If True, skips discovery and evaluates existing database leads.
        target_tiers: List of priority tiers to include in outreach. Defaults to [TIER_1, TIER_2].
        skip_outreach: If True, skips outreach campaign dispatch.

    Returns:
        Tuple of (DiscoveryStatistics, ClassificationStatistics, OutreachStatistics, DatabaseStatsDict).
    """
    effective_test_mode = config.TEST_MODE if test_mode is None else test_mode
    effective_dry_run = config.DRY_RUN if dry_run is None else dry_run
    effective_query = config.SEARCH_KEYWORD if query is None else query
    if target_tiers is None:
        target_tiers = [TIER_1, TIER_2]

    disc_stats = DiscoveryStatistics()
    class_stats = ClassificationStatistics()

    print("=" * 72)
    print("EXPORT AUTOMATION SYSTEM -- END-TO-END PIPELINE (PHASES 1 - 7)")
    print(f"Target Product : {effective_query}")
    print(f"Execution Mode : {'TEST_MODE (Simulation / Offline)' if effective_test_mode else 'LIVE PRODUCTION MODE'}")
    print(f"Outreach Mode  : {'DRY-RUN (Simulated Dispatches)' if effective_dry_run else 'LIVE SMTP DISPATCH'}")
    print(f"Gemini Model   : {config.GEMINI_MODEL}")
    print(f"Daily Limit    : {config.DAILY_SEND_LIMIT} emails/day")
    print(f"SQLite DB Path : {config.DB_PATH.name}")
    print(f"PDF Catalog    : {config.PRESENTATION_PATH.name} ({'Found' if config.PRESENTATION_PATH.exists() else 'Missing'})")
    print(f"Data Directory : {config.DATA_DIR}")
    print("=" * 72)

    # --------------------------------------------------------------------------
    # STEP 0: DATABASE INITIALIZATION & CSV MIGRATION
    # --------------------------------------------------------------------------
    init_database()
    init_buyers_csv()
    init_sent_log()
    init_activity_log()

    # Automatically ensure historical CSV data is migrated to SQLite
    migration_counts = migrate_csv_to_sqlite()
    if any(count > 0 for count in migration_counts.values()):
        log_activity(
            event="DATABASE_MIGRATION",
            email="",
            status="SUCCESS",
            message=f"Migrated records to SQLite: {migration_counts}",
            print_console=False,
        )

    log_activity(
        event="PIPELINE_INIT",
        email="",
        status="INFO",
        message=f"Initialized pipeline. TEST_MODE={effective_test_mode}, DRY_RUN={effective_dry_run}.",
    )

    # --------------------------------------------------------------------------
    # STEP 1: LEAD DISCOVERY & EXTRACTION
    # --------------------------------------------------------------------------
    existing_buyers = read_all_buyers()
    if not existing_buyers:
        existing_buyers = get_all_buyers()
    newly_saved_leads: List[Dict[str, str]] = []

    if skip_discovery:
        print("\n[Step 1] Lead Discovery skipped (--no-discovery flag). Using existing catalog.")
    else:
        print(f"\n[Step 1] Discovering buyer leads across search adapters (limit={limit})...")
        raw_leads = discover_all_leads(
            query=effective_query,
            limit=limit,
            test_mode=effective_test_mode,
        )
        print(f"-> Discovered {len(raw_leads)} raw results from Google, Directories, and Websites.\n")

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
    
    catalog_to_classify = existing_buyers if existing_buyers else newly_saved_leads
    classified_leads: List[Tuple[Dict[str, str], LeadClassification]] = []

    for buyer in catalog_to_classify:
        email = buyer.get("email", "")
        if not email:
            continue

        classification = classify_lead(buyer, use_ai=True, test_mode=effective_test_mode)
        class_stats.record(classification)
        classified_leads.append((buyer, classification))

        # Attach classification fields to buyer dictionary for outreach step
        buyer["tier"] = classification.tier
        buyer["outreach_angle"] = classification.outreach_angle
        buyer["intent_score"] = str(classification.intent_score)
        buyer["classification"] = classification.category

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
    # STEP 4: AUTOMATED OUTREACH CAMPAIGN (PHASE 4)
    # --------------------------------------------------------------------------
    if skip_outreach:
        print("\n--- Step 4: Outreach Campaign Skipped (--no-outreach flag) ---")
        outreach_results: List[OutreachResult] = []
        outreach_stats = OutreachStatistics()
    else:
        print("\n--- Step 4: Automated Outreach Campaign Dispatch ---")
        
        can_send, sent_today, max_limit = can_send_today()
        print(f"Daily Mailbox Quota: {sent_today}/{max_limit} emails dispatched today.")

        target_leads = [b for b, _ in classified_leads]

        outreach_results, outreach_stats = send_batch_outreach(
            buyers=target_leads,
            target_tiers=target_tiers,
            dry_run=effective_dry_run,
            test_mode=effective_test_mode,
            delay_seconds=0.0,
        )

        for res in outreach_results:
            status_tag = f"[{res.status[:8]}]"
            print(f"  {status_tag:<10} {res.email:<32} | {res.message}")

    # --------------------------------------------------------------------------
    # STEP 5: SUMMARY & STATISTICAL REPORTS
    # --------------------------------------------------------------------------
    print()
    if not skip_discovery:
        disc_stats.print_summary()

    print("\n" + "=" * 72)
    print("PHASE 3: AI LEAD CLASSIFICATION & TIER REPORT")
    print("=" * 72)
    print(f"Total Leads Evaluated        : {class_stats.total_evaluated}")
    print(f"B2B Wholesale / Studios      : {class_stats.business_count}")
    print(f"B2C Solo / Personal Buyers   : {class_stats.individual_count}")
    print(f"Irrelevant / Unqualified     : {class_stats.irrelevant_count}")
    print("-" * 72)
    print(f"Tier 1 (High Priority Bulk)  : {class_stats.tier_1_count}")
    print(f"Tier 2 (Medium Priority)     : {class_stats.tier_2_count}")
    print(f"Tier 3 (Low Priority Solo)   : {class_stats.tier_3_count}")
    print("=" * 72)

    print("\n" + "=" * 72)
    print("PHASE 4: OUTREACH & EMAIL AUTOMATION REPORT")
    print("=" * 72)
    print(f"Targeted Qualified Leads     : {outreach_stats.total_targeted}")
    print(f"Dispatched via Live SMTP     : {outreach_stats.sent_count}")
    print(f"Simulated Dispatches (Dry-Run): {outreach_stats.simulated_count}")
    print(f"Skipped: Previously Contacted: {outreach_stats.skipped_duplicate}")
    print(f"Skipped: Daily Limit Reached : {outreach_stats.skipped_daily_limit}")
    print(f"Rejected: Invalid Syntax     : {outreach_stats.rejected_count}")
    print(f"Failed Transmission Errors   : {outreach_stats.failed_count}")
    print(f"Catalog Presentation Attached: {'assets/company_presentation.pdf (Active)' if config.PRESENTATION_PATH.exists() else 'None'}")
    print("=" * 72)

    # --------------------------------------------------------------------------
    # STEP 6: PHASE 5 SQLITE DATABASE SUMMARY REPORT
    # --------------------------------------------------------------------------
    db_stats = get_database_stats()
    print("\n" + "=" * 72)
    print("PHASE 5: ENTERPRISE SQLITE DATABASE REPORT (export_automation.db)")
    print("=" * 72)
    print(f"Relational Database Location : {config.DB_PATH}")
    print(f"Master Cataloged Buyers      : {db_stats['total_buyers']}")
    print(f"B2B Wholesale / Studio Leads : {db_stats['business_buyers']}")
    print(f"B2C Solo / Personal Buyers   : {db_stats['individual_buyers']}")
    print("-" * 72)
    print(f"Tier 1 Priority Buyers in DB : {db_stats['tier_1_count']}")
    print(f"Tier 2 Priority Buyers in DB : {db_stats['tier_2_count']}")
    print(f"Tier 3 Priority Buyers in DB : {db_stats['tier_3_count']}")
    print("-" * 72)
    print(f"Outreach Dispatches in DB    : {db_stats['outreach_success'] + db_stats['outreach_simulated']}")
    print(f"Total Audit Trail Events     : {db_stats['total_activities']}")
    print("=" * 72)

    return disc_stats, class_stats, outreach_stats, db_stats


def main() -> None:
    """CLI execution entrypoint."""
    args = parse_args()

    tier_map = {
        "1": TIER_1,
        "tier1": TIER_1,
        "2": TIER_2,
        "tier2": TIER_2,
        "3": TIER_3,
        "tier3": TIER_3,
    }
    raw_tiers = [t.strip().lower() for t in args.tier.split(",") if t.strip()]
    target_tiers = [tier_map[t] for t in raw_tiers if t in tier_map]
    if not target_tiers:
        target_tiers = [TIER_1, TIER_2]

    run_pipeline(
        test_mode=args.test_mode,
        dry_run=args.dry_run,
        query=args.query,
        limit=args.limit,
        skip_discovery=args.no_discovery,
        target_tiers=target_tiers,
        skip_outreach=args.no_outreach,
    )


if __name__ == "__main__":
    main()
