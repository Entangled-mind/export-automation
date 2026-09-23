"""Buyer AI classification module for EXPORT Automation System.

Categorizes discovered contacts into:
- BUSINESS (B2B wholesale importers, studios, wellness centers, retailers)
- INDIVIDUAL (B2C personal buyers, retail shoppers, individual practitioners)

Supports Google Gemini API when GEMINI_API_KEY is configured, and provides
an intelligent, explainable rule-based heuristic fallback for offline or zero-key environments.
"""

import json
import re
from typing import Dict, Optional, Tuple
import urllib.request
import urllib.error

import config

# Common freemail/consumer domains that typically signify individuals (unless corporate evidence exists)
FREEMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "mail.com",
    "protonmail.com",
    "zoho.com",
}

# High-confidence B2B / corporate indicators in company name, email, or source
BUSINESS_KEYWORDS = {
    "wholesale",
    "wholesaler",
    "wholesalers",
    "importer",
    "importers",
    "import",
    "imports",
    "studio",
    "studios",
    "center",
    "centre",
    "spa",
    "wellness",
    "supplies",
    "gear",
    "gmbh",
    "ltd",
    "llc",
    "inc",
    "corp",
    "co.",
    "company",
    "trading",
    "enterprises",
    "distribution",
    "distributor",
    "distributors",
    "sound healing",
    "yoga",
    "meditation",
    "handicrafts",
    "academy",
    "clinic",
    "shop",
    "store",
}


def heuristic_classify(buyer: Dict[str, str]) -> Tuple[str, str, float]:
    """Rule-based heuristic classifier for B2B vs B2C buyer contacts.

    Evaluates:
    1. Presence and keywords in `company_name`.
    2. Email domain (corporate custom domain vs consumer freemail).
    3. Presence of a business website.

    Args:
        buyer: Normalized buyer dictionary.

    Returns:
        Tuple of (category: 'BUSINESS' | 'INDIVIDUAL', reasoning: str, confidence: float).
    """
    company = (buyer.get("company_name") or "").strip().lower()
    email = (buyer.get("email") or "").strip().lower()
    website = (buyer.get("website") or "").strip().lower()

    email_domain = email.split("@")[-1] if "@" in email else ""
    is_freemail = email_domain in FREEMAIL_DOMAINS

    # Check for strong business keywords in company name
    matched_keywords = [kw for kw in BUSINESS_KEYWORDS if kw in company]

    # Rule 1: Clear company name with business keywords
    if company and matched_keywords:
        return (
            "BUSINESS",
            f"Strong commercial indicators in company name ('{buyer.get('company_name')}') with terms: {', '.join(matched_keywords[:3])}.",
            0.95,
        )

    # Rule 2: Corporate custom domain + presence of company name
    if company and not is_freemail and email_domain:
        return (
            "BUSINESS",
            f"Has registered company ('{buyer.get('company_name')}') and dedicated corporate domain (@{email_domain}).",
            0.90,
        )

    # Rule 3: Corporate domain even with sparse company name, provided website exists
    if not is_freemail and website and email_domain:
        return (
            "BUSINESS",
            f"Commercial web domain (@{email_domain}) with active website ({website}).",
            0.80,
        )

    # Rule 4: Explicit company name even on freemail (e.g. small studio using gmail)
    if company and len(company) > 3:
        return (
            "BUSINESS",
            f"Identified business entity ('{buyer.get('company_name')}'), operating via {email_domain}.",
            0.75,
        )

    # Rule 5: Individual/B2C (freemail, no company name)
    if is_freemail or not company:
        return (
            "INDIVIDUAL",
            f"Personal consumer profile: no commercial entity listed; uses consumer email service (@{email_domain or 'unknown'}).",
            0.85,
        )

    return (
        "INDIVIDUAL",
        "Insufficient corporate indicators detected; defaulted to individual inquiry.",
        0.60,
    )


def gemini_classify(buyer: Dict[str, str], api_key: str) -> Optional[Tuple[str, str, float]]:
    """Classify a buyer contact using Google Gemini API.

    Sends a structured prompt requesting classification into BUSINESS or INDIVIDUAL.

    Args:
        buyer: Normalized buyer dictionary.
        api_key: Valid Google Gemini API key.

    Returns:
        Tuple of (category, reasoning, confidence) or None if request fails.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={api_key}"

    prompt = f"""You are an export sales analyst for a Singing Bowls manufacturer.
Classify the following contact into either "BUSINESS" (B2B: wholesaler, distributor, yoga/sound studio, wellness center, gift shop, importer) or "INDIVIDUAL" (B2C: retail buyer, personal hobbyist).

Buyer Details:
- Name: {buyer.get('buyer_name', '')}
- Company: {buyer.get('company_name', '')}
- Email: {buyer.get('email', '')}
- Website: {buyer.get('website', '')}
- Country: {buyer.get('country', '')}
- Source: {buyer.get('source_platform', '')}

Respond ONLY with valid JSON in this exact structure:
{{"category": "BUSINESS" or "INDIVIDUAL", "reasoning": "brief explanation under 25 words", "confidence": 0.9}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(content_text)
            category = parsed.get("category", "INDIVIDUAL").strip().upper()
            if category not in ("BUSINESS", "INDIVIDUAL"):
                category = "INDIVIDUAL"
            reasoning = parsed.get("reasoning", "Classified via Gemini AI.")
            confidence = float(parsed.get("confidence", 0.9))
            return category, f"[Gemini AI] {reasoning}", confidence
    except Exception:
        # Graceful fallback on network or API failure
        return None


def classify_buyer(buyer: Dict[str, str]) -> Tuple[str, str, float]:
    """Classify a buyer contact as BUSINESS (B2B) or INDIVIDUAL (B2C).

    Utilizes Gemini AI when GEMINI_API_KEY is configured; otherwise uses the
    rule-based heuristic classifier.

    Args:
        buyer: Normalized buyer dictionary.

    Returns:
        Tuple of (category: 'BUSINESS' | 'INDIVIDUAL', reasoning: str, confidence: float).
    """
    api_key = config.GEMINI_API_KEY.strip()
    if api_key:
        result = gemini_classify(buyer, api_key)
        if result:
            return result

    # Standard / Fallback heuristic classification
    category, reasoning, confidence = heuristic_classify(buyer)
    return category, f"[Heuristic] {reasoning}", confidence
