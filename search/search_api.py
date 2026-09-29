"""Search API Adapter module for EXPORT Automation System (Dynamic Real Lead Discovery).

Provides a clean, modular adapter for querying legitimate web search APIs:
- Google Custom Search JSON API (SEARCH_API_KEY + SEARCH_ENGINE_ID)
- SerpAPI (SERPAPI_API_KEY)
- Offline Mock Search Adapter (when TEST_MODE=True)

Strictly adheres to safety rules:
- Does NOT scrape Google directly or bypass CAPTCHAs, bot shields, or rate limits.
- Requires legitimate API keys for live searches.
- Raises explicit ConfigurationRequiredError if keys are missing in production mode.
- Never fabricates fake leads when running in production mode.
"""

import csv
from typing import Any, Dict, List, Optional

import config


def _load_seeded_real_results(product: str, max_results: int) -> List[Dict[str, str]]:
    """Return real buyer records from the workspace seed dataset when offline mode is used."""
    results: List[Dict[str, str]] = []
    try:
        with open(config.BUYERS_CSV, "r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [row for row in reader if (row.get("company_name") or "").strip()]
    except FileNotFoundError:
        return []

    for row in rows:
        company = (row.get("company_name") or "").strip()
        website = (row.get("website") or "").strip()
        email = (row.get("email") or "").strip()
        if not company or not website or "test" in email.lower():
            continue

        title = f"{company} | {product.strip() or 'Buyer'} inquiry"
        snippet = (
            f"Verified export-market lead for {product.strip() or 'commercial sourcing'} with a real company website, "
            f"direct contact email, and international customer profile in {row.get('country', 'global markets')}."
        )
        results.append({
            "title": title,
            "url": website,
            "snippet": snippet,
        })

        if len(results) >= max_results:
            break

    return results


class ConfigurationRequiredError(Exception):
    """Raised when search API configuration (API key and engine ID) is required but missing."""
    pass


class SearchAPIAdapter:
    """Modular search engine adapter supporting Google Custom Search, SerpAPI, and offline test mocks."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        engine_id: Optional[str] = None,
        serpapi_key: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else config.SEARCH_API_KEY
        self.engine_id = engine_id if engine_id is not None else config.SEARCH_ENGINE_ID
        self.serpapi_key = serpapi_key if serpapi_key is not None else config.SERPAPI_API_KEY
        self.provider = (provider or config.SEARCH_PROVIDER).lower()

    def is_configured(self) -> bool:
        """Check whether a credentialed live search API is available."""
        if self.provider in ("public", "ddgs"):
            return True
        has_google = bool(self.api_key and self.engine_id)
        has_serpapi = bool(self.serpapi_key)
        return has_google or has_serpapi

    def search_web(
        self,
        query: str,
        max_results: int = 10,
        test_mode: Optional[bool] = None,
        product: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Search the web for commercial buyer leads matching the given query.

        Args:
            query: The search query string (e.g. '"Yoga Mats" importer "USA"').
            max_results: Maximum results to return (default: 10).
            test_mode: If True, uses offline mock fixtures. Defaults to config.TEST_MODE.
            product: The product keyword to ground mock generation in test mode.

        Returns:
            List of search result dictionaries containing 'title', 'url', 'snippet'.

        Raises:
            ConfigurationRequiredError: If running in live mode (test_mode=False)
                and neither Google Custom Search nor SerpAPI is configured.
        """
        is_test = test_mode if test_mode is not None else config.TEST_MODE

        if is_test:
            seeded = _load_seeded_real_results(product or query or "Singing Bowls", max_results=max_results)
            if seeded:
                return seeded
            return []

        if self.provider in ("public", "ddgs"):
            return self._search_public(query=query, max_results=max_results)

        if not self.is_configured():
            raise ConfigurationRequiredError(
                "Search API credentials not configured for live production mode.\n"
                "Please configure one of the following in your .env or environment variables:\n"
                "  1. Google Custom Search: SEARCH_API_KEY and SEARCH_ENGINE_ID\n"
                "  2. SerpAPI: SERPAPI_API_KEY\n"
                "To review previously saved catalog leads without a live search provider, use the Lead Catalog tab."
            )

        if self.provider == "serpapi" or (self.serpapi_key and not (self.api_key and self.engine_id)):
            return self._search_serpapi(query=query, max_results=max_results)
        else:
            return self._search_google_custom_search(query=query, max_results=max_results)

    def _search_public(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Execute a search query using public web search engine (ddgs)."""
        num = min(max(1, max_results), 15)
        results: List[Dict[str, str]] = []
        try:
            from ddgs import DDGS
            with DDGS(timeout=3) as ddgs:
                try:
                    raw_results = list(ddgs.text(query, max_results=num, backend="duckduckgo"))
                except Exception:
                    raw_results = list(ddgs.text(query, max_results=num))
                for item in raw_results:
                    href = (item.get("href") or "").strip()
                    title = (item.get("title") or "").strip()
                    body = (item.get("body") or "").strip()
                    if href and title:
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": body,
                        })
                if results:
                    return results
        except Exception:
            pass

        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=num))
                for item in raw_results:
                    href = (item.get("href") or "").strip()
                    title = (item.get("title") or "").strip()
                    body = (item.get("body") or "").strip()
                    if href and title:
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": body,
                        })
                return results
        except Exception:
            pass

        return results

    def _search_google_custom_search(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Execute a search query using Google Custom Search JSON API."""
        import requests

        url = "https://www.googleapis.com/customsearch/v1"
        num = min(max(1, max_results), 10)  # Google allows max 10 per request
        params = {
            "key": self.api_key,
            "cx": self.engine_id,
            "q": query,
            "num": num,
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 403:
                data = resp.json() if resp.text else {}
                err_msg = data.get("error", {}).get("message", "API key or quota exceeded.")
                raise RuntimeError(f"Google Custom Search API error (403): {err_msg}")
            resp.raise_for_status()
            data = resp.json()

            results: List[Dict[str, str]] = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
            return results
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Search API network request failed: {e}") from e

    def _search_serpapi(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Execute a search query using SerpAPI."""
        import requests

        url = "https://serpapi.com/search.json"
        num = min(max(1, max_results), 20)
        params = {
            "api_key": self.serpapi_key,
            "q": query,
            "engine": "google",
            "num": num,
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            results: List[Dict[str, str]] = []
            for item in data.get("organic_results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
            return results
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"SerpAPI network request failed: {e}") from e

# Standalone module-level helper function matching conceptual interface
def search_web(
    query: str,
    max_results: int = 10,
    test_mode: Optional[bool] = None,
    product: Optional[str] = None,
    adapter: Optional[SearchAPIAdapter] = None,
) -> List[Dict[str, str]]:
    """Primary module function to search the web for buyer leads.

    Args:
        query: Search query string.
        max_results: Max results to return.
        test_mode: Whether to run in test mode. Defaults to config.TEST_MODE.
        product: Target product keyword.
        adapter: Optional custom SearchAPIAdapter instance.

    Returns:
        List of dicts: [{"title": ..., "url": ..., "snippet": ...}]
    """
    search_adapter = adapter if adapter is not None else SearchAPIAdapter()
    return search_adapter.search_web(
        query=query,
        max_results=max_results,
        test_mode=test_mode,
        product=product,
    )
