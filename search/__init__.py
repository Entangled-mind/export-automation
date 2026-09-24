"""Modular Search and Lead Discovery package for EXPORT Automation System.

Provides adapters for permitted and public data discovery:
- search.google_search: Simulated and public search results
- search.directory_search: Structured business directory parsing via BeautifulSoup
- search.website_search: Webpage contact extraction and public text email scraping

All adapters return standardized buyer lead records adhering to the core schema:
{
    "buyer_name": str,
    "company_name": str,
    "email": str,
    "website": str,
    "country": str,
    "source_platform": str
}
"""

from typing import Dict, List, Optional

import config
from search.directory_search import parse_directory_html, search_directory
from search.google_search import search_google
from search.website_search import (
    extract_contacts_from_html,
    extract_emails_from_text,
    search_website,
)


def discover_all_leads(
    query: Optional[str] = None,
    limit: int = 15,
    test_mode: Optional[bool] = None,
) -> List[Dict[str, str]]:
    """Aggregate raw prospective buyer leads across all modular search adapters.

    In TEST_MODE, this strictly uses offline sample fixtures without any
    external HTTP requests, rate limit triggers, or scraping.

    Args:
        query: Product or market search query (defaults to config.SEARCH_KEYWORD).
        limit: Maximum total leads to collect.
        test_mode: Explicit test mode flag (defaults to config.TEST_MODE).

    Returns:
        List of standardized raw buyer dictionaries.
    """
    if query is None:
        query = config.SEARCH_KEYWORD
    if test_mode is None:
        test_mode = config.TEST_MODE

    discovered: List[Dict[str, str]] = []

    # 1. Google / Public Search Adapter
    google_leads = search_google(query=query, limit=5, test_mode=test_mode)
    discovered.extend(google_leads)

    # 2. Business Directory Adapter
    dir_leads = search_directory(limit=5, test_mode=test_mode)
    discovered.extend(dir_leads)

    # 3. Direct Website Extraction Adapter
    web_leads = search_website(limit=5, test_mode=test_mode)
    discovered.extend(web_leads)

    return discovered[:limit]
