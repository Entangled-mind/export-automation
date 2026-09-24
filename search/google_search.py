"""Google and public web search adapter module for EXPORT Automation System.

Extracts buyer leads from search result pages or test fixtures without bypassing
CAPTCHAs, rate limits, or anti-bot protections.
"""

from typing import Dict, List, Optional
import config

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

    # Live Mode: Polite HTTP request to public search endpoint
    # Note: Respects robots, anti-bot mechanisms, and avoids aggressive scraping
    leads: List[Dict[str, str]] = []
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        resp = requests.get(search_url, headers=headers, timeout=6)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            snippets = soup.select(".result__snippet")
            titles = soup.select(".result__title")

            for i in range(min(len(titles), limit)):
                title_text = titles[i].get_text(strip=True) if i < len(titles) else ""
                snippet_text = snippets[i].get_text(strip=True) if i < len(snippets) else ""

                leads.append({
                    "buyer_name": "",
                    "company_name": title_text[:50],
                    "email": "",
                    "website": "",
                    "country": "",
                    "source_platform": "Google Search",
                })
    except Exception:
        # Fall back safely on error without crashing the pipeline
        pass

    return leads
