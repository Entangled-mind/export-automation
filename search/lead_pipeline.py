"""Dynamic Lead Discovery Pipeline module for EXPORT Automation System.

Orchestrates the 8-step pipeline to find real, publicly available B2B buyer leads
for any user-provided product and optional country filter:
1. Input validation & query generation
2. Search API query execution (Google Custom Search, SerpAPI, or Offline Test Mock)
3. Raw search results aggregation
4. Public website business information extraction & relevance filtering
5. Data quality validation & status assignment (VALID, INCOMPLETE, INVALID_EMAIL, DUPLICATE, REJECTED)
6. Deduplication (by email and company + website)
7. SQLite database persistence (export_automation.db)
8. Normalized reporting & metric counters
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import config
from database.repository import get_buyer_by_email, upsert_buyer
from database.schema import init_database
from extraction.data_extractor import normalize_email
from search.query_generator import generate_buyer_queries
from search.search_api import ConfigurationRequiredError, SearchAPIAdapter, search_web
from search.website_extractor import extract_business_info, extract_emails_from_text, is_placeholder_email
from validation.email_validator import is_valid_email


def run_discovery_pipeline(
    product: str,
    country: Optional[str] = None,
    region: Optional[str] = None,
    buyer_type: Optional[str] = None,
    additional_context: Optional[str] = None,
    max_results: int = 20,
    test_mode: Optional[bool] = None,
    save_to_db: bool = True,
    db_path: Optional[Path] = None,
    search_adapter: Optional[SearchAPIAdapter] = None,
    allow_public_fallback: bool = True,
) -> Dict[str, Any]:
    """Execute end-to-end dynamic B2B buyer discovery for a product.

    Args:
        product: The product/keyword to discover buyers for (e.g. 'Yoga Mats', 'Organic Tea').
        country: Optional geographic/country filter (e.g. 'USA', 'Germany', 'UK').
        max_results: Maximum target number of leads to discover (default: 20).
        test_mode: Whether to run in offline test simulation mode. Defaults to config.TEST_MODE.
        save_to_db: Whether to persist qualified discovered leads to SQLite database.
        db_path: Optional custom path to SQLite database.
        search_adapter: Optional custom SearchAPIAdapter instance.
        allow_public_fallback: Whether to use public search provider when API keys are not set.

    Returns:
        Dictionary containing metric counters, queries used, and discovered leads.

    Raises:
        ValueError: If product keyword is empty.
        ConfigurationRequiredError: If live mode is requested without API credentials and fallback disabled.
    """
    clean_product = (product or "").strip()
    if not clean_product:
        raise ValueError("Product/keyword input is required. Please provide a product name.")

    clean_country = (country or "").strip() if country else None
    is_test = test_mode if test_mode is not None else config.TEST_MODE

    # Initialize SQLite database schema
    active_db = init_database(db_path)

    adapter = search_adapter if search_adapter is not None else SearchAPIAdapter()
    queries = generate_buyer_queries(
        product=clean_product,
        country=clean_country,
        region=region,
        buyer_type=buyer_type,
        additional_context=additional_context,
        include_extended=False,
    )[:8]
    searches_performed = 0
    raw_results_collected: List[Dict[str, str]] = []
    seen_urls: Set[str] = set()
    errors: List[str] = []

    # 2. Execute Web Searches via legitimate API adapter
    # If live mode without API keys, check if public search fallback is allowed
    if not is_test and not adapter.is_configured():
        if allow_public_fallback:
            adapter = SearchAPIAdapter(provider="public")
        else:
            raise ConfigurationRequiredError(
                "Search API configuration required for live lead discovery. "
                "Please configure SEARCH_API_KEY & SEARCH_ENGINE_ID (or SERPAPI_API_KEY) in your .env file. "
                "To test offline without API keys, enable TEST_MODE=true."
            )

    for q in queries:
        if len(raw_results_collected) >= min(max_results * 2, 24):
            break
        try:
            searches_performed += 1
            results = adapter.search_web(
                query=q,
                max_results=min(10, max_results),
                test_mode=is_test,
                product=clean_product,
            )
            for res in results:
                u = (res.get("url") or "").strip()
                if u:
                    from urllib.parse import urlparse
                    host = (urlparse(u).hostname or "").lower().removeprefix("www.")
                    dedup_key = host or u.rstrip("/").lower()
                    if dedup_key in seen_urls:
                        continue
                    seen_urls.add(dedup_key)
                    # Associate the query that surfaced this result. Keep one page per
                    # company host so a site with many URLs cannot crowd out other buyers.
                    res_copy = dict(res)
                    res_copy["search_query"] = q
                    raw_results_collected.append(res_copy)
        except Exception as e:
            # Handle query failure gracefully: log error and continue
            errors.append(f"Query '{q}' failed: {e}")

    # 3. Process Public Websites & Extract Business Information
    websites_processed = 0
    leads_discovered = 0
    raw_extracted_leads: List[Dict[str, Any]] = []

    for item in raw_results_collected:
        if len(raw_extracted_leads) >= max_results:
            break
        target_url = item.get("url", "")
        search_q = item.get("search_query", "")

        websites_processed += 1
        try:
            info = extract_business_info(
                url=target_url,
                product_keyword=clean_product,
                search_query=search_q,
                timeout=6.0,
                test_mode=is_test,
            )
            if info:
                # Search snippets occasionally expose a business email that is absent
                # from the rendered page. Keep only syntactically valid, non-placeholder
                # addresses and record that the listing itself was the source.
                if not info.get("email"):
                    snippet_emails = extract_emails_from_text(item.get("snippet", ""))
                    public_email = next((e for e in snippet_emails if is_valid_email(e) and not is_placeholder_email(e)), "")
                    if public_email:
                        info["email"] = public_email
                        info["email_source"] = "Public search listing; verify before sending"
                        info["contact_source_url"] = target_url
                # Preserve the exact public page that produced this lead for auditability.
                info.setdefault("source_url", target_url)
                info.setdefault("website", target_url)
                leads_discovered += 1
                # Keep country blank when it is not found on the public page. The
                # requested target market is a search filter, not proof of location.
                raw_extracted_leads.append(info)
            else:
                snippet_emails = extract_emails_from_text(item.get("snippet", ""))
                public_email = next((e for e in snippet_emails if is_valid_email(e) and not is_placeholder_email(e)), "")
                raw_extracted_leads.append({
                    "buyer_name": "",
                    "company_name": (item.get("title") or "").strip(),
                    "email": public_email,
                    "email_source": "Public search listing; verify before sending" if public_email else "",
                    "contact_source_url": target_url if public_email else "",
                    "website": target_url,
                    "country": clean_country or "",
                    "source_platform": "Live web search result",
                    "source_url": target_url,
                    "search_query": search_q,
                    "validation_status": config.STATUS_INCOMPLETE,
                    "validation_reason": "Website contact could not be verified automatically.",
                    "product": clean_product,
                    "unverified_search_result": True,
                })
        except Exception as e:
            # Handle single website failure gracefully without crashing pipeline
            errors.append(f"Extraction failed for '{target_url}': {e}")

    # 4. Data Quality Validation, Normalization & Deduplication
    processed_leads: List[Dict[str, Any]] = []
    seen_batch_emails: Set[str] = set()
    seen_batch_companies: Set[Tuple[str, str]] = set()

    valid_emails_count = 0
    duplicates_removed_count = 0

    for lead in raw_extracted_leads:
        normalized_lead = dict(lead)
        raw_email = normalized_lead.get("email") or ""
        clean_email = normalize_email(raw_email)
        company_name = (normalized_lead.get("company_name") or "").strip()
        website = (normalized_lead.get("website") or "").strip()
        buyer_name = (normalized_lead.get("buyer_name") or "").strip()
        country_name = (normalized_lead.get("country") or "").strip()

        normalized_lead["email"] = clean_email
        normalized_lead["company_name"] = company_name
        normalized_lead["website"] = website
        normalized_lead["source_url"] = (
            normalized_lead.get("source_url") or website
        ).strip()
        normalized_lead["buyer_name"] = buyer_name
        normalized_lead["country"] = country_name
        normalized_lead["product"] = clean_product

        # Determine validation status
        status = normalized_lead.get("validation_status", config.STATUS_VALID)

        # Check if already rejected by relevance filter
        if status == config.STATUS_REJECTED:
            normalized_lead["validation_status"] = config.STATUS_REJECTED
            processed_leads.append(normalized_lead)
            continue

        # Check email validity
        if not clean_email:
            normalized_lead["validation_status"] = config.STATUS_INCOMPLETE
            processed_leads.append(normalized_lead)
            continue

        if not is_valid_email(clean_email) or is_placeholder_email(clean_email):
            normalized_lead["validation_status"] = config.STATUS_INVALID_EMAIL
            processed_leads.append(normalized_lead)
            continue

        # Check Deduplication:
        # A) Within current discovery batch
        company_key = (company_name.lower(), website.lower())
        is_dup_in_batch = (clean_email in seen_batch_emails) or (
            company_name and website and company_key in seen_batch_companies
        )

        # B) Against existing SQLite database
        existing_in_db = False
        if active_db and active_db.exists():
            try:
                existing_record = get_buyer_by_email(clean_email, db_path=active_db)
                if existing_record:
                    existing_in_db = True
            except Exception:
                pass

        if is_dup_in_batch or existing_in_db:
            duplicates_removed_count += 1
            normalized_lead["validation_status"] = config.STATUS_DUPLICATE
            processed_leads.append(normalized_lead)
            continue

        # Mark seen
        seen_batch_emails.add(clean_email)
        if company_name and website:
            seen_batch_companies.add(company_key)

        # Check completeness
        if not company_name or not website:
            normalized_lead["validation_status"] = config.STATUS_INCOMPLETE
        else:
            normalized_lead["validation_status"] = config.STATUS_VALID

        valid_emails_count += 1

        # 5. Database Persistence
        if save_to_db:
            try:
                upsert_buyer(normalized_lead, db_path=active_db)
            except Exception as e:
                errors.append(f"Database save error for {clean_email}: {e}")

        processed_leads.append(normalized_lead)

    return {
        "product": clean_product,
        "country": clean_country or "All",
        "searches_performed": searches_performed,
        "raw_results_count": len(raw_results_collected),
        "websites_processed": websites_processed,
        "leads_discovered": leads_discovered,
        "valid_emails": valid_emails_count,
        "duplicates_removed": duplicates_removed_count,
        "leads": processed_leads,
        "queries": queries,
        "errors": errors,
        "test_mode": is_test,
    }


def run_multi_product_search(
    products: Optional[List[str]] | str = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    buyer_type: Optional[str] = None,
    additional_context: Optional[str] = None,
    max_results_per_product: int = 20,
    test_mode: Optional[bool] = None,
    save_to_db: bool = True,
    db_path: Optional[Path] = None,
    search_adapter: Optional[SearchAPIAdapter] = None,
) -> Dict[str, Any]:
    """Run discovery for multiple product keywords and aggregate the results."""
    if isinstance(products, str):
        normalized_products = [p.strip() for p in products.split(",") if p.strip()]
    elif products is None:
        normalized_products = []
    else:
        normalized_products = [str(p).strip() for p in products if str(p).strip()]

    if not normalized_products:
        raise ValueError("At least one product keyword is required.")

    aggregated_products: List[Dict[str, Any]] = []
    all_leads: List[Dict[str, Any]] = []
    total_searches = 0
    total_raw = 0
    total_websites = 0
    total_discovered = 0
    total_valid_emails = 0
    total_duplicates = 0

    for product in normalized_products:
        result = run_discovery_pipeline(
            product=product,
            country=country,
            region=region,
            buyer_type=buyer_type,
            additional_context=additional_context,
            max_results=max_results_per_product,
            test_mode=test_mode,
            save_to_db=save_to_db,
            db_path=db_path,
            search_adapter=search_adapter,
        )

        product_entry = {
            "product": product,
            "country": result.get("country", country or "All"),
            "searches_performed": result.get("searches_performed", 0),
            "raw_results_count": result.get("raw_results_count", 0),
            "websites_processed": result.get("websites_processed", 0),
            "leads_discovered": result.get("leads_discovered", 0),
            "valid_emails": result.get("valid_emails", 0),
            "duplicates_removed": result.get("duplicates_removed", 0),
            "leads": result.get("leads", []),
            "queries": result.get("queries", []),
            "errors": result.get("errors", []),
        }
        aggregated_products.append(product_entry)

        for lead in result.get("leads", []):
            lead_copy = dict(lead)
            lead_copy["product"] = product
            all_leads.append(lead_copy)

        total_searches += product_entry["searches_performed"]
        total_raw += product_entry["raw_results_count"]
        total_websites += product_entry["websites_processed"]
        total_discovered += product_entry["leads_discovered"]
        total_valid_emails += product_entry["valid_emails"]
        total_duplicates += product_entry["duplicates_removed"]

    return {
        "products": aggregated_products,
        "all_leads": all_leads,
        "product_count": len(aggregated_products),
        "leads_discovered": total_discovered,
        "searches_performed": total_searches,
        "raw_results_count": total_raw,
        "websites_processed": total_websites,
        "valid_emails": total_valid_emails,
        "duplicates_removed": total_duplicates,
        "country": country or "All",
        "test_mode": test_mode,
    }
