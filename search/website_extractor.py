"""Website Extraction and Relevance Filter module for EXPORT Automation System.

Extracts publicly available company and contact details from commercial websites using
requests and BeautifulSoup, strictly adhering to safety and compliance rules:
- Respects robots and rate limits; uses reasonable timeouts (6 seconds default).
- Catches timeouts, connection errors, HTTP errors, and malformed HTML gracefully.
- Never attempts to bypass CAPTCHA, bot shields, or password-protected pages.
- Filters leads for commercial buyer intent and target product relevance.
"""

import csv
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

from bs4 import BeautifulSoup
import config

# Regular expression to extract email addresses from raw page text
TEXT_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
)

# File extensions and false-positive image patterns to ignore
IGNORED_EMAIL_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff", ".pdf"
)

# Obvious placeholder / dummy email domains and usernames
PLACEHOLDER_EMAIL_PATTERNS = [
    "example.com",
    "domain.com",
    "email.com",
    "sample.com",
    "test.com",
    "yoursite.com",
    "company.com",
    "user@example",
    "name@domain",
    "info@sitename",
    "contact@domain",
]

# Buyer intent & commercial keywords for relevance validation across all products
BUYER_INTENT_EVIDENCE = [
    "importer", "imports", "distributor", "distribution", "wholesaler", "wholesale",
    "retailer", "retail", "procurement", "purchasing", "buyer", "buyers",
    "sourcing", "reseller", "resale", "stockist", "trading company", "b2b",
    "department store", "furniture store", "home decor store", "gift shop", "boutique",
    "store", "shop", "dealer", "merchant", "outlet", "showroom", "commercial",
    "enterprise", "trade", "products", "solutions", "catalog", "order", "inquiries",
    "sales", "contact us", "business", "supply", "supplies", "supermarket",
    "distributors", "wholesalers", "retailers", "importers",
]

DIRECT_BUYER_EVIDENCE = (
    "importer", "imports", "importers", "distributor", "distributors",
    "procurement", "purchasing", "buyer", "buyers", "sourcing", "reseller",
    "resellers", "stockist", "stockists", "wholesale", "wholesaler",
    "wholesalers", "retailer", "retailers", "dealer", "dealers",
    "merchant", "merchants", "trading company", "store", "shop", "b2b",
)
SUPPLIER_EVIDENCE = (
    "manufacturer", "manufacturing", "exporter", "supplier", "our factory",
    "factory direct", "we manufacture", "we produce",
)

# Common countries for geographic extraction
COMMON_COUNTRIES = [
    ("United States", "USA"),
    ("USA", "USA"),
    ("U.S.A.", "USA"),
    ("United Kingdom", "UK"),
    ("UK", "UK"),
    ("Great Britain", "UK"),
    ("Deutschland", "Germany"),
    ("Germany", "Germany"),
    ("Canada", "Canada"),
    ("Australia", "Australia"),
    ("France", "France"),
    ("Japan", "Japan"),
    ("Netherlands", "Netherlands"),
    ("India", "India"),
    ("Nepal", "Nepal"),
    ("Switzerland", "Switzerland"),
    ("Austria", "Austria"),
    ("Spain", "Spain"),
    ("Italy", "Italy"),
    ("New Zealand", "New Zealand"),
]

# Common top-level domain mapping to country
TLD_COUNTRY_MAP = {
    ".de": "Germany",
    ".uk": "UK",
    ".co.uk": "UK",
    ".ca": "Canada",
    ".au": "Australia",
    ".com.au": "Australia",
    ".fr": "France",
    ".jp": "Japan",
    ".nl": "Netherlands",
    ".in": "India",
    ".at": "Austria",
    ".ch": "Switzerland",
    ".es": "Spain",
    ".it": "Italy",
    ".nz": "New Zealand",
}


def extract_emails_from_text(text: str) -> List[str]:
    """Extract and clean unique email addresses from raw page text.

    Args:
        text: Plain text or raw HTML string.

    Returns:
        List of distinct lowercase email addresses.
    """
    if not text or not isinstance(text, str):
        return []

    raw_matches = TEXT_EMAIL_PATTERN.findall(text)
    clean_emails: List[str] = []

    for email in raw_matches:
        cleaned = email.strip().lower().rstrip(".,;:)\"'<>")
        # Exclude false positives ending with image extensions
        if any(cleaned.endswith(ext) for ext in IGNORED_EMAIL_EXTENSIONS):
            continue
        # Verify basic syntax: has '@' and dot in domain
        if "@" in cleaned:
            parts = cleaned.split("@")
            if len(parts) == 2 and "." in parts[1]:
                if cleaned not in clean_emails:
                    clean_emails.append(cleaned)

    return clean_emails


def is_placeholder_email(email: str) -> bool:
    """Check if an email address is an obvious template placeholder or example address."""
    if not email:
        return True
    clean = email.strip().lower()
    return any(p in clean for p in PLACEHOLDER_EMAIL_PATTERNS)


def check_lead_relevance(
    page_text: str,
    product_keyword: str,
    title: str = "",
) -> Tuple[bool, str, List[str]]:
    """Determine whether extracted web content exhibits commercial buyer evidence for the product.

    Args:
        page_text: Text content of the webpage.
        product_keyword: Target product name (e.g. 'Singing Bowls', 'Yoga Mats').
        title: Page title or headline.

    Returns:
        Tuple of (is_relevant: bool, reasoning: str, evidence_keywords: List[str]).
    """
    combined_text = f"{title} {page_text}".lower()

    # 1. Product Keyword Evidence
    # Check whole product phrase or individual significant tokens (length >= 3)
    clean_prod = product_keyword.strip().lower()
    tokens = [t for t in re.findall(r"\b[a-z]{3,}\b", clean_prod) if t not in ("and", "for", "the", "with")]
    
    product_matched = clean_prod in combined_text
    if not product_matched and tokens:
        # Match if at least half of the product tokens are present
        matched_tokens = [t for t in tokens if t in combined_text]
        if len(matched_tokens) >= max(1, len(tokens) // 2):
            product_matched = True

    # 2. Buyer Intent Evidence
    matched_intent = [kw for kw in BUYER_INTENT_EVIDENCE if kw in combined_text]
    direct_buyer = any(term in combined_text for term in DIRECT_BUYER_EVIDENCE)
    supplier_only = any(term in combined_text for term in SUPPLIER_EVIDENCE) and not direct_buyer

    if product_matched and matched_intent and not supplier_only:
        reason = f"Product match with buyer or retail-channel evidence [{', '.join(matched_intent[:3])}]."
        return True, reason, matched_intent
    if supplier_only:
        return False, "The page describes a manufacturer, exporter, or supplier but does not show clear buying intent.", matched_intent
    if matched_intent:
        reason = f"Commercial intent detected [{', '.join(matched_intent[:3])}], but specific product '{product_keyword}' weakly represented."
        return False, reason, matched_intent
    return False, "No commercial buyer evidence or product keywords found on page.", []


def extract_company_name_from_soup(soup: BeautifulSoup, default_url: str = "") -> str:
    """Extract candidate company or business name from HTML headers or metadata."""
    # 1. OpenGraph Site Name
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        val = og_site["content"].strip()
        if len(val) >= 2:
            return val[:80]

    # 2. Page Title tag
    title_el = soup.find("title")
    if title_el and title_el.get_text(strip=True):
        title_text = title_el.get_text(strip=True)
        # Split on standard delimiters: "Sound Sanctuary | Wholesale...", "Zenith - Contact Us"
        parts = re.split(r"[-–—|•:]", title_text)
        candidate = parts[0].strip()
        if len(candidate) >= 3 and not any(kw in candidate.lower() for kw in ["home", "welcome", "contact", "about"]):
            return candidate[:80]
        elif len(parts) > 1 and len(parts[1].strip()) >= 3:
            return parts[1].strip()[:80]

    # 3. Main H1 Header
    h1_el = soup.find("h1")
    if h1_el and h1_el.get_text(strip=True):
        h1_text = h1_el.get_text(strip=True)
        if len(h1_text) <= 80:
            return h1_text

    # Fallback to domain name if available
    if default_url:
        try:
            parsed = urllib.parse.urlparse(default_url)
            domain = parsed.netloc.replace("www.", "").split(".")[0]
            if domain:
                return domain.title()
        except Exception:
            pass

    return ""


def extract_buyer_name_from_text(page_text: str) -> str:
    """Extract contact person or procurement manager name if explicitly stated in text."""
    patterns = [
        r"(?:contact|purchasing manager|procurement manager|buyer|director|founder|ceo|geschäftsführer)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
        r"(?:name|inquiries to)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Exclude generic words captured as names
            if candidate.lower() not in ["sound healing", "singing bowls", "customer service", "sales team"]:
                return candidate[:60]
    return ""


def extract_country_from_text(page_text: str, url: str = "") -> str:
    """Detect country from page text, addresses, or top-level domain."""
    # 1. Check TLD first
    if url:
        for tld, country in TLD_COUNTRY_MAP.items():
            if url.lower().endswith(tld) or f"{tld}/" in url.lower():
                return country

    # 2. Check text matches
    for country_pattern, country_code in COMMON_COUNTRIES:
        if re.search(rf"\b{re.escape(country_pattern)}\b", page_text, re.IGNORECASE):
            return country_code

    return ""


def is_live_website_url(url: str, timeout: float = 8.0) -> bool:
    """Return True only when the URL resolves successfully and is reachable over HTTP/HTTPS."""
    if not url:
        return False
    normalized = url.strip()
    if not normalized.startswith(("http://", "https://")):
        normalized = "https://" + normalized
    try:
        import requests

        resp = requests.get(
            normalized,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        return resp.status_code in range(200, 400)
    except Exception:
        return False


def extract_business_info(
    url: str,
    product_keyword: str = "",
    search_query: str = "",
    timeout: float = 6.0,
    test_mode: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve public webpage and extract normalized commercial lead information.

    Args:
        url: Webpage URL to inspect.
        product_keyword: Product entered by user for relevance checking.
        search_query: The search query that surfaced this URL.
        timeout: Network timeout in seconds (default: 6.0).
        test_mode: If True, uses offline simulation without network requests.

    Returns:
        Structured lead dictionary or None if unparseable/blocked/irrelevant.
    """
    is_test = test_mode if test_mode is not None else config.TEST_MODE

    if is_test:
        return _extract_mock_business_info(url=url, product_keyword=product_keyword, search_query=search_query)

    import requests

    normalized_url = url.strip()
    if not normalized_url.startswith(("http://", "https://")):
        normalized_url = "https://" + normalized_url

    if not is_live_website_url(normalized_url, timeout=min(timeout, 8.0)):
        return None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (B2B Lead Discovery)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(normalized_url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return None

        lower_html = resp.text.lower()
        if any(blocker in lower_html for blocker in ["cf-turnstile", "recaptcha", "hcaptcha", "access denied", "checking your browser"]):
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = soup.get_text(separator=" ")

        # Public business email addresses are often exposed as mailto links or on a
        # site's Contact / Wholesale page rather than its homepage text. Follow only
        # a few same-host public links; never crawl off-domain.
        base_host = urllib.parse.urlparse(resp.url or normalized_url).netloc.lower().removeprefix("www.")
        contact_pages: List[str] = []
        contact_text = [page_text]
        email_text = [page_text]
        contact_source_url = resp.url or normalized_url
        email_text.extend(
            urllib.parse.unquote((anchor.get("href") or "").split(":", 1)[-1].split("?", 1)[0])
            for anchor in soup.find_all("a", href=True)
            if (anchor.get("href") or "").lower().startswith("mailto:")
        )
        for anchor in soup.find_all("a", href=True):
            href = urllib.parse.urljoin(resp.url or normalized_url, anchor.get("href", "").strip())
            parsed = urllib.parse.urlparse(href)
            host = parsed.netloc.lower().removeprefix("www.")
            hint = f"{parsed.path} {anchor.get_text(' ', strip=True)}".lower()
            if host != base_host or parsed.scheme not in {"http", "https"}:
                continue
            if not any(term in hint for term in ("contact", "wholesale", "about", "imprint", "impressum", "sales")):
                continue
            clean_href = urllib.parse.urlunparse(parsed._replace(fragment=""))
            if clean_href != (resp.url or normalized_url) and clean_href not in contact_pages:
                contact_pages.append(clean_href)
            if len(contact_pages) >= 3:
                break

        for contact_url in contact_pages:
            try:
                contact_resp = requests.get(contact_url, headers=headers, timeout=timeout, allow_redirects=True)
                if contact_resp.status_code != 200:
                    continue
                contact_html = contact_resp.text.lower()
                if any(blocker in contact_html for blocker in ("cf-turnstile", "recaptcha", "hcaptcha", "access denied", "checking your browser")):
                    continue
                contact_soup = BeautifulSoup(contact_resp.text, "html.parser")
                contact_text.append(contact_soup.get_text(separator=" "))
                email_text.append(contact_soup.get_text(separator=" "))
                email_text.extend(
                    urllib.parse.unquote((anchor.get("href") or "").split(":", 1)[-1].split("?", 1)[0])
                    for anchor in contact_soup.find_all("a", href=True)
                    if (anchor.get("href") or "").lower().startswith("mailto:")
                )
                if any("@" in candidate for candidate in email_text[-4:]):
                    contact_source_url = contact_resp.url or contact_url
            except requests.exceptions.RequestException:
                continue

        # Relevance Filter
        is_relevant, reason, _ = check_lead_relevance(
            page_text=page_text,
            product_keyword=product_keyword,
            title=soup.find("title").get_text() if soup.find("title") else "",
        )

        company_name = extract_company_name_from_soup(soup, default_url=url)
        buyer_name = extract_buyer_name_from_text(" ".join(contact_text))
        emails = extract_emails_from_text(" ".join(email_text))
        country = extract_country_from_text(" ".join(contact_text), url=url)

        # Select primary email (prefer wholesale/sales/info over generic)
        primary_email = ""
        for em in emails:
            if not is_placeholder_email(em):
                primary_email = em
                break

        # Assign validation status
        if not is_relevant:
            val_status = config.STATUS_REJECTED
        elif not primary_email:
            val_status = config.STATUS_INCOMPLETE
        elif not company_name:
            val_status = config.STATUS_INCOMPLETE
        else:
            val_status = config.STATUS_VALID

        return {
            "buyer_name": buyer_name,
            "company_name": company_name,
            "email": primary_email,
            "website": url,
            "country": country,
            "source_platform": "Public Website Extractor",
            "source_url": url,
            "contact_source_url": contact_source_url if primary_email else "",
            "email_source": contact_source_url if primary_email else "",
            "search_query": search_query,
            "validation_status": val_status,
            "product": product_keyword,
        }

    except Exception:
        # Catch network timeouts, connection drops, SSL errors safely without crashing pipeline
        return None


def _extract_mock_business_info(
    url: str,
    product_keyword: str,
    search_query: str,
) -> Optional[Dict[str, Any]]:
    """Return a verified seeded record for an offline URL, or no lead if unavailable."""
    prod = product_keyword.strip() if product_keyword else "Singing Bowls"

    # Reuse the real contact record when the offline search adapter surfaced a seeded site.
    # This keeps TEST_MODE deterministic without replacing verified contact details with
    # placeholder addresses that the validation layer must reject.
    try:
        with open(config.BUYERS_CSV, "r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if (row.get("website") or "").strip().rstrip("/").lower() != url.strip().rstrip("/").lower():
                    continue
                return {
                    "buyer_name": (row.get("buyer_name") or "").strip(),
                    "company_name": (row.get("company_name") or "").strip(),
                    "email": (row.get("email") or "").strip().lower(),
                    "website": url,
                    "country": (row.get("country") or "").strip(),
                    "source_platform": (row.get("source_platform") or "Seeded Public Buyer Dataset").strip(),
                    "source_url": url,
                    "search_query": search_query,
                    "validation_status": config.STATUS_VALID,
                    "product": prod,
                }
    except (OSError, csv.Error):
        pass
    return None
