"""Google and public web search adapter module for EXPORT Automation System.

Extracts buyer leads from search result pages or test fixtures without bypassing
CAPTCHAs, rate limits, or anti-bot protections.
"""

from typing import Dict, List, Optional
import config
from search.search_api import SearchAPIAdapter

# Curated test fixtures representing realistic Google search results
# for Singing Bowls wholesale importers and distributors
TEST_GOOGLE_LEADS: List[Dict[str, str]] = [
    {
        "buyer_name": "Maya Lin",
        "company_name": "Sound Sanctuary Studio",
        "email": "contact@soundsanctuary.com",
        "website": "https://www.soundsanctuary.com",
        "country": "USA",
        "source_platform": "Google Search",
    },
    {
        "buyer_name": "Klaus Weber",
        "company_name": "Himalayan Art & Sound GmbH",
        "email": "purchasing@himalayan-sound.de",
        "website": "https://www.himalayan-sound.de",
        "country": "Germany",
        "source_platform": "Google Search",
    },
    {
        "buyer_name": "Liam Gallagher",
        "company_name": "Dharma Meditation Wholesalers",
        "email": "orders@dharmameditation.co.uk",
        "website": "https://www.dharmameditation.co.uk",
        "country": "UK",
        "source_platform": "Google Search",
    },
    {
        "buyer_name": "Chloe Bennett",
        "company_name": "Zenith Sound & Wellness Spa",
        "email": "procurement@zenithspa.ca",
        "website": "https://www.zenithspa.ca",
        "country": "Canada",
        "source_platform": "Google Search",
    },
    {
        "buyer_name": "Michael Vance",
        "company_name": "",
        "email": "michael.vance88@gmail.com",
        "website": "",
        "country": "USA",
        "source_platform": "Google Search",
    },
]


def search_google(
    query: Optional[str] = None,
    limit: int = 5,
    test_mode: Optional[bool] = None,
) -> List[Dict[str, str]]:
    """Discover buyer contacts via search engine queries or offline fixtures.

    Args:
        query: Search keywords (e.g. 'Singing Bowls wholesale imports studio').
        limit: Maximum number of search results to return.
        test_mode: Whether to run in offline TEST_MODE. Defaults to config.TEST_MODE.

    Returns:
        List of standardized buyer lead dictionaries.
    """
    if query is None:
        query = config.SEARCH_KEYWORD
    if test_mode is None:
        test_mode = config.TEST_MODE

    # In TEST_MODE, return safe offline sample fixtures immediately
    if test_mode:
        results = []
        for lead in TEST_GOOGLE_LEADS[:limit]:
            results.append(dict(lead))
        return results

    # Live mode uses official, credentialed search APIs only.
    listings = SearchAPIAdapter().search_web(query=query, max_results=limit, test_mode=False)
    return [
        {
            "buyer_name": "",
            "company_name": (item.get("title") or "").strip(),
            "email": "",
            "website": (item.get("url") or "").strip(),
            "country": "",
            "source_platform": "Configured Search API",
        }
        for item in listings
    ]
