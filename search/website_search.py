"""Website contact extraction adapter module for EXPORT Automation System.

Extracts publicly available company names, buyer names, emails, and country
information from webpage HTML and publicly displayed page text using regex and BeautifulSoup.
"""

import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import config

# Regular expression to extract email addresses from raw page text
TEXT_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
)

# Common image/file extensions to ignore in regex email matching
IGNORED_EMAIL_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")

TEST_WEBSITE_PAGES = [
    {
        "url": "https://www.zenithspa.ca/contact",
        "html": """
        <html>
            <head><title>Contact Us - Zenith Sound & Wellness Spa</title></head>
            <body>
                <header><h1>Zenith Sound & Wellness Spa</h1></header>
                <div class="content">
                    <p>For wholesale singing bowl orders and procurement inquiries, contact our procurement manager Chloe Bennett.</p>
                    <p>Direct inquiries: procurement@zenithspa.ca or info@zenithspa.ca</p>
                    <p>Location: Toronto, Ontario, Canada</p>
                </div>
                <footer>© 2026 Zenith Sound & Wellness Spa. All rights reserved.</footer>
            </body>
        </html>
        """,
    },
    {
        "url": "https://www.alpinesound.de/impressum",
        "html": """
        <html>
            <head><title>Impressum - Alpine Sound Healing Studio GmbH</title></head>
            <body>
                <div class="impressum">
                    <h2>Alpine Sound Healing Studio GmbH</h2>
                    <p>Geschäftsführer: Marcus Vance</p>
                    <p>Email: wholesale@alpinesound.de</p>
                    <p>Land: Germany / Deutschland</p>
                </div>
            </body>
        </html>
        """,
    },
    {
        "url": "https://www.soundhobbyist.org/about",
        "html": """
        <html>
            <head><title>About Us - Sound Meditation Enthusiast</title></head>
            <body>
                <h1>Sound Meditation Enthusiast</h1>
                <p>Hi, I am Sarah Miller. I practice sound healing at home.</p>
                <p>Email me at sarah.meditation@gmail.com for tips.</p>
                <p>Based in United Kingdom</p>
            </body>
        </html>
        """,
    },
]


def extract_emails_from_text(text: str) -> List[str]:
    """Extract email addresses from publicly displayed page text.

    Args:
        text: Plain text or raw HTML string.

    Returns:
        List of distinct, cleaned email addresses found in the text.
    """
    if not text or not isinstance(text, str):
        return []

    matches = TEXT_EMAIL_PATTERN.findall(text)
    clean_emails = []

    for email in matches:
        cleaned = email.strip().lower().rstrip(".,;:)")
        # Filter out false positives (e.g. image filenames)
        if any(cleaned.endswith(ext) for ext in IGNORED_EMAIL_EXTENSIONS):
            continue
        if "@" in cleaned and "." in cleaned.split("@")[1]:
            if cleaned not in clean_emails:
                clean_emails.append(cleaned)

    return clean_emails


def extract_contacts_from_html(
    html_content: str,
    source_url: str = "",
) -> List[Dict[str, str]]:
    """Extract company and contact records from a webpage's HTML.

    Args:
        html_content: HTML page source.
        source_url: The URL the page was retrieved from.

    Returns:
        List of standardized buyer lead dictionaries.
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    page_text = soup.get_text(separator=" ")

    # Extract all emails displayed on the page
    emails = extract_emails_from_text(page_text)

    # Attempt to extract company name from title or h1
    title_el = soup.find("title")
    h1_el = soup.find("h1")

    company_name = ""
    if h1_el:
        company_name = h1_el.get_text(strip=True)
    elif title_el:
        company_name = title_el.get_text(strip=True).split("-")[0].strip()

    # Detect country mentions from common names
    common_countries = ["USA", "Germany", "Canada", "UK", "United Kingdom", "India", "Australia", "Nepal"]
    detected_country = ""
    for c in common_countries:
        if re.search(rf"\b{re.escape(c)}\b", page_text, re.IGNORECASE):
            detected_country = "UK" if c == "United Kingdom" else c
            break

    contacts: List[Dict[str, str]] = []

    if emails:
        for email in emails:
            contacts.append({
                "buyer_name": "",
                "company_name": company_name[:60],
                "email": email,
                "website": source_url,
                "country": detected_country,
                "source_platform": "Website Search",
            })
    else:
        contacts.append({
            "buyer_name": "",
            "company_name": company_name[:60],
            "email": "",
            "website": source_url,
            "country": detected_country,
            "source_platform": "Website Search",
        })

    return contacts


def search_website(
    target_url: str = "",
    limit: int = 5,
    test_mode: Optional[bool] = None,
) -> List[Dict[str, str]]:
    """Discover buyer contacts by parsing target company websites.

    Args:
        target_url: URL to scrape (in live mode).
        limit: Max records to return.
        test_mode: Whether to run in offline TEST_MODE. Defaults to config.TEST_MODE.

    Returns:
        List of standardized buyer lead dictionaries.
    """
    if test_mode is None:
        test_mode = config.TEST_MODE

    # In TEST_MODE, extract from bundled sample pages without network requests
    if test_mode or not target_url:
        results = []
        for sample in TEST_WEBSITE_PAGES:
            leads = extract_contacts_from_html(sample["html"], source_url=sample["url"])
            results.extend(leads)
        return results[:limit]

    # Live Mode: Polite request to target website
    try:
        import requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(target_url, headers=headers, timeout=6)
        if resp.status_code == 200:
            return extract_contacts_from_html(resp.text, source_url=target_url)[:limit]
    except Exception:
        pass

    return []
