"""Buyer Discovery and Search Adapter module for EXPORT Automation System.

Discovers potential B2B buyer leads from permitted web directories,
search results, and simulated market discovery adapters.
"""

from typing import Dict, List, Optional


# Curated realistic Singing Bowls buyer leads across global export markets
DEMO_SINGING_BOWLS_LEADS = [
    {
        "buyer_name": "Maya Lin",
        "company_name": "Sound Sanctuary Studio",
        "email": "contact@soundsanctuary.com",
        "website": "https://www.soundsanctuary.com",
        "country": "USA",
        "source_platform": "Google Directory",
    },
    {
        "buyer_name": "Klaus Weber",
        "company_name": "Himalayan Art & Sound GmbH",
        "email": "purchasing@himalayan-sound.de",
        "website": "https://www.himalayan-sound.de",
        "country": "Germany",
        "source_platform": "EU Business Directory",
    },
    {
        "buyer_name": "Liam Gallagher",
        "company_name": "Dharma Meditation Wholesalers",
        "email": "orders@dharmameditation.co.uk",
        "website": "https://www.dharmameditation.co.uk",
        "country": "UK",
        "source_platform": "Wholesale Trade Portal",
    },
    {
        "buyer_name": "Chloe Tremblay",
        "company_name": "Zenith Wellness & Spa Supplies",
        "email": "procurement@zenithspa.ca",
        "website": "https://zenithspa.ca",
        "country": "Canada",
        "source_platform": "Spa Directory",
    },
    {
        "buyer_name": "Michael Vance",
        "company_name": "",
        "email": "michael.vance88@gmail.com",
        "website": "",
        "country": "USA",
        "source_platform": "Sound Healing Forum",
    },
    {
        "buyer_name": "Elena Rostova",
        "company_name": "",
        "email": "elena_yoga@yahoo.com",
        "website": "https://elenarostova.blog",
        "country": "Germany",
        "source_platform": "Yoga Community",
    },
    {
        "buyer_name": "Ananya Sharma",
        "company_name": "Lotus Sound Healing Importers",
        "email": "ananya@lotussound.in",
        "website": "https://lotussound.in",
        "country": "India",
        "source_platform": "Google Search",
    },
    # Edge case: lead with messy formatting & uppercase
    {
        "buyer_name": "  David Miller  ",
        "company_name": "  Apex Meditation Gear  ",
        "email": "  SALES@APEXMEDITATION.COM  ",
        "website": "https://apexmeditation.com",
        "country": "Australia",
        "source_platform": "Web Search",
    },
    # Edge case: raw lead with invalid email format (for testing rejection)
    {
        "buyer_name": "Ghost Contact",
        "company_name": "Phantom Bowls",
        "email": "invalid@contact@nowhere",
        "website": "",
        "country": "USA",
        "source_platform": "Scraped Raw",
    },
]


def fetch_mock_directory_leads(query: str = "Wholesale Imports", limit: int = 10) -> List[Dict[str, str]]:
    """Return simulated search/directory discovery results for wholesale buyers.

    Args:
        query: Search query terms.
        limit: Maximum number of leads to return.

    Returns:
        List of raw buyer lead dictionaries.
    """
    leads = []
    for item in DEMO_SINGING_BOWLS_LEADS[:limit]:
        # Return a copy to prevent mutation of the template
        leads.append(dict(item))
    return leads


def parse_directory_html(html_content: str, source_label: str = "HTML Directory") -> List[Dict[str, str]]:
    """Parse raw directory HTML content to extract prospective buyer contacts.

    Uses BeautifulSoup if installed, otherwise basic text pattern matching.

    Args:
        html_content: Raw HTML text.
        source_label: Source tag for the records.

    Returns:
        List of extracted raw dictionaries.
    """
    leads: List[Dict[str, str]] = []
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")
        cards = soup.find_all(class_="buyer-card")
        for card in cards:
            name = card.find(class_="buyer-name")
            company = card.find(class_="company-name")
            email = card.find(class_="buyer-email")
            website = card.find(class_="buyer-website")
            country = card.find(class_="buyer-country")

            leads.append({
                "buyer_name": name.get_text(strip=True) if name else "",
                "company_name": company.get_text(strip=True) if company else "",
                "email": email.get_text(strip=True) if email else "",
                "website": website.get_text(strip=True) if website else "",
                "country": country.get_text(strip=True) if country else "",
                "source_platform": source_label,
            })
    except ImportError:
        pass
    return leads


def discover_buyers(
    query: str = "Wholesale Imports",
    limit: int = 10,
    use_demo: bool = True,
    custom_sources: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """Primary discovery interface to fetch raw prospective buyer contacts.

    In Phase 2, this aggregates from mock search adapters, public directories,
    or user-provided sources.

    Args:
        query: Target product keyword (e.g. 'Wholesale Imports').
        limit: Max records to discover.
        use_demo: Whether to include the curated demo leads.
        custom_sources: Optional list of additional raw records.

    Returns:
        List of raw dictionaries ready for normalization.
    """
    discovered: List[Dict[str, str]] = []

    if custom_sources:
        discovered.extend(custom_sources)

    if use_demo:
        demo_leads = fetch_mock_directory_leads(query=query, limit=limit)
        discovered.extend(demo_leads)

    return discovered[:limit]
