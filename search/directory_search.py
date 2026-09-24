"""Business directory search and parsing adapter module for EXPORT Automation System.

Extracts structured buyer information from public trade directory cards and tables
using BeautifulSoup.
"""

from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import config

TEST_DIRECTORY_HTML = """
<div class="directory-list">
    <article class="directory-card">
        <h3 class="company-name">Himalayan Resonance Imports</h3>
        <p class="contact-person">Elena Rostova</p>
        <span class="email-address">elena_yoga@yahoo.com</span>
        <a class="website-link" href="https://www.himalayanresonance.com">Website</a>
        <span class="country-badge">Australia</span>
    </article>
    <article class="directory-card">
        <h3 class="company-name">Apex Sound Healing Supplies</h3>
        <p class="contact-person">David Chen</p>
        <span class="email-address">sales@apexmeditation.com</span>
        <a class="website-link" href="https://www.apexmeditation.com">Website</a>
        <span class="country-badge">USA</span>
    </article>
    <article class="directory-card">
        <h3 class="company-name">Lotus Sound & Meditation Ltd</h3>
        <p class="contact-person">Ananya Sharma</p>
        <span class="email-address">ananya@lotussound.in</span>
        <a class="website-link" href="https://www.lotussound.in">Website</a>
        <span class="country-badge">India</span>
    </article>
    <article class="directory-card">
        <h3 class="company-name">Tibetan Harmony Wholesalers</h3>
        <p class="contact-person">Heinrich Bauer</p>
        <span class="email-address">orders@tibetan-harmony.de</span>
        <a class="website-link" href="https://www.tibetan-harmony.de">Website</a>
        <span class="country-badge">Germany</span>
    </article>
    <article class="directory-card">
        <h3 class="company-name">Incomplete Directory Entry</h3>
        <p class="contact-person">Test Incomplete</p>
        <span class="email-address"></span>
        <a class="website-link" href="">Website</a>
        <span class="country-badge"></span>
    </article>
</div>
"""


def parse_directory_html(
    html_content: str,
    source_label: str = "Business Directory",
) -> List[Dict[str, str]]:
    """Parse raw directory HTML content to extract prospective buyer contacts.

    Extracts:
    - company_name
    - buyer_name (contact person)
    - email
    - website
    - country

    Args:
        html_content: Raw HTML text of the directory page or snippet.
        source_label: Identifier for source_platform.

    Returns:
        List of standardized buyer lead dictionaries.
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    extracted_leads: List[Dict[str, str]] = []

    # Look for article cards, divs, or table rows
    cards = soup.select(".directory-card, .buyer-card, .listing-card")

    if not cards:
        # Fallback to generic article or container parsing
        cards = soup.find_all("article")

    for card in cards:
        # 1. Company Name
        comp_el = card.select_one(".company-name, .company, h3, h4")
        company = comp_el.get_text(strip=True) if comp_el else ""

        # 2. Buyer Name
        buyer_el = card.select_one(".buyer-name, .contact-person, .contact, p")
        buyer = buyer_el.get_text(strip=True) if buyer_el else ""

        # 3. Email Address
        email_el = card.select_one(".buyer-email, .email-address, .email")
        email = email_el.get_text(strip=True) if email_el else ""
        if not email and card.find("a", href=lambda h: h and "mailto:" in h):
            mailto = card.find("a", href=lambda h: h and "mailto:" in h)
            email = mailto["href"].replace("mailto:", "").split("?")[0].strip()

        # 4. Website Link
        web_el = card.select_one(".buyer-website, .website-link, a")
        website = web_el.get("href", "").strip() if web_el else ""
        if website.startswith("mailto:"):
            website = ""

        # 5. Country
        country_el = card.select_one(".buyer-country, .country-badge, .country")
        country = country_el.get_text(strip=True) if country_el else ""

        extracted_leads.append({
            "buyer_name": buyer,
            "company_name": company,
            "email": email,
            "website": website,
            "country": country,
            "source_platform": source_label,
        })

    return extracted_leads


def search_directory(
    directory_url: Optional[str] = None,
    limit: int = 5,
    test_mode: Optional[bool] = None,
) -> List[Dict[str, str]]:
    """Discover buyer contacts from business directories.

    Args:
        directory_url: URL to public directory.
        limit: Max records to return.
        test_mode: Whether to run offline. Defaults to config.TEST_MODE.

    Returns:
        List of standardized buyer lead dictionaries.
    """
    if test_mode is None:
        test_mode = config.TEST_MODE

    # In TEST_MODE, parse sample directory HTML without network requests
    if test_mode or not directory_url:
        leads = parse_directory_html(TEST_DIRECTORY_HTML, source_label="Directory")
        return leads[:limit]

    # Live Mode: Polite request to public directory
    try:
        import requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(directory_url, headers=headers, timeout=6)
        if resp.status_code == 200:
            leads = parse_directory_html(resp.text, source_label="Business Directory")
            return leads[:limit]
    except Exception:
        pass

    return []
