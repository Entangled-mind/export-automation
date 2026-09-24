"""Buyer AI classification module for EXPORT Automation System (Phase 3).

Specialized for Himalayan Singing Bowls export products:
- Hand-hammered 7-Metals Tibetan Singing Bowls
- 7-Chakra tuned singing bowl sets for sound baths & therapy
- Machine-crafted bronze & brass bowls for retail meditation centers
- Acoustic accessories (wooden mallets, felt strikers, brocade cushions, ting-sha cymbals, gongs)

Classifies prospective buyer leads into:
- Category: BUSINESS (B2B Wholesale / Studios / Spas), INDIVIDUAL (Solo / Personal), IRRELEVANT (Spam / Unrelated)
- Priority Tier:
    * Tier 1 - High Priority (Wholesalers, Importers, Global Distributors, Volume Buyers)
    * Tier 2 - Medium Priority (Independent Studios, Sound Healing Centers, Spas, Boutiques)
    * Tier 3 - Low Priority (Solo Practitioners, Retail Shoppers, Hobbyists)
    * Irrelevant / Unqualified (Spam, Unrelated Industries)
- Intent Score: 0 - 100 quantitative B2B purchase volume & fit score
- Outreach Angle: Tailored product pitch recommendation for cold outreach
- Reasoning: Concise explanation of the classification decision

Supports Google Gemini API with fallback to offline mock evaluation in TEST_MODE
and rule-based domain heuristics.
"""

from dataclasses import asdict, dataclass
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

import config

# Try importing official Google GenAI SDK
try:
    from google import genai
    from google.genai import types

    GENAI_SDK_AVAILABLE = True
except ImportError:
    GENAI_SDK_AVAILABLE = False


# ==============================================================================
# CLASSIFICATION & TIER CONSTANTS
# ==============================================================================
CATEGORY_BUSINESS = config.CATEGORY_BUSINESS
CATEGORY_INDIVIDUAL = config.CATEGORY_INDIVIDUAL
CATEGORY_IRRELEVANT = config.CATEGORY_IRRELEVANT

TIER_1 = config.TIER_1
TIER_2 = config.TIER_2
TIER_3 = config.TIER_3
TIER_IRRELEVANT = config.TIER_IRRELEVANT

# Freemail domains representing personal consumers unless corporate evidence exists
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

# High-volume B2B wholesale / importer indicators (Tier 1)
WHOLESALE_KEYWORDS = {
    "wholesale",
    "wholesaler",
    "wholesalers",
    "importer",
    "importers",
    "import",
    "imports",
    "distributor",
    "distributors",
    "distribution",
    "bulk",
    "trading",
    "export",
    "impex",
}

# General corporate entity legal suffixes
CORPORATE_SUFFIXES = {
    "gmbh",
    "ltd",
    "llc",
    "inc",
    "corp",
    "co.",
    "b.v.",
    "pty",
    "enterprises",
    "supplies",
}

# Commercial studio, spa, sound healing & therapy indicators
STUDIO_WELLNESS_KEYWORDS = {
    "sound healing",
    "sound bath",
    "singing bowls",
    "tibetan",
    "meditation",
    "yoga",
    "wellness",
    "spa",
    "retreat",
    "therapy",
    "therapist",
    "chakra",
    "harmonic",
    "gong",
    "reiki",
    "holistic",
    "sanctuary",
    "studio",
    "studios",
    "academy",
    "center",
    "centre",
    "clinic",
    "shop",
    "store",
    "boutique",
    "handicrafts",
    "esoteric",
    "spiritual",
}

# Negative / false positive indicators (unrelated industries)
IRRELEVANT_KEYWORDS = {
    "software",
    "saas",
    "crypto",
    "bitcoin",
    "logistics",
    "trucking",
    "construction",
    "plumbing",
    "automotive",
    "real estate",
    "petroleum",
    "oil",
    "insurance",
    "dentistry",
    "dental",
    "pharma",
    "cybersecurity",
}

# Consolidated for backward compatibility
BUSINESS_KEYWORDS = WHOLESALE_KEYWORDS | STUDIO_WELLNESS_KEYWORDS | CORPORATE_SUFFIXES


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class LeadClassification:
    """Represents the structured result of an AI/heuristic lead evaluation."""

    category: str
    tier: str
    intent_score: int
    confidence: float
    outreach_angle: str
    reasoning: str
    source: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert classification result to a dictionary."""
        return asdict(self)


@dataclass
class ClassificationStatistics:
    """Aggregates execution metrics for Phase 3 lead classification."""

    total_evaluated: int = 0
    business_count: int = 0
    individual_count: int = 0
    irrelevant_count: int = 0
    tier_1_count: int = 0
    tier_2_count: int = 0
    tier_3_count: int = 0
    ai_count: int = 0
    heuristic_count: int = 0

    def record(self, result: LeadClassification) -> None:
        """Record a single classification result."""
        self.total_evaluated += 1
        if result.category == CATEGORY_BUSINESS:
            self.business_count += 1
        elif result.category == CATEGORY_INDIVIDUAL:
            self.individual_count += 1
        else:
            self.irrelevant_count += 1

        if result.tier == TIER_1:
            self.tier_1_count += 1
        elif result.tier == TIER_2:
            self.tier_2_count += 1
        elif result.tier == TIER_3:
            self.tier_3_count += 1

        if "Gemini" in result.source:
            self.ai_count += 1
        else:
            self.heuristic_count += 1

    def summary(self) -> Dict[str, int]:
        """Return metrics as a dictionary."""
        return {
            "total_evaluated": self.total_evaluated,
            "business_count": self.business_count,
            "individual_count": self.individual_count,
            "irrelevant_count": self.irrelevant_count,
            "tier_1_count": self.tier_1_count,
            "tier_2_count": self.tier_2_count,
            "tier_3_count": self.tier_3_count,
            "ai_count": self.ai_count,
            "heuristic_count": self.heuristic_count,
        }


# ==============================================================================
# PROMPT ENGINEERING & JSON PARSING
# ==============================================================================
def build_classification_prompt(buyer: Dict[str, str]) -> str:
    """Construct a specialized prompt evaluating buyer fit for Singing Bowls export.

    Args:
        buyer: Normalized buyer dictionary.

    Returns:
        Structured text prompt for Google Gemini AI.
    """
    return f"""You are a senior B2B international trade analyst specializing in Himalayan acoustic sound healing instruments (Tibetan Singing Bowls, 7-Chakra sets, meditation gongs, bronze healing bells, and accessories).

Analyze the prospective international buyer lead below and classify their commercial viability.

Prospective Buyer Profile:
- Contact Name: {buyer.get('buyer_name', 'Unknown')}
- Company Name: {buyer.get('company_name', 'None listed')}
- Email: {buyer.get('email', '')}
- Website: {buyer.get('website', 'None listed')}
- Country: {buyer.get('country', 'Unknown')}
- Discovery Channel: {buyer.get('source_platform', 'Unknown')}

Your tasks:
1. Determine the broad category:
   - "BUSINESS" (B2B: wholesaler, distributor, sound studio, yoga center, spa, wellness retailer)
   - "INDIVIDUAL" (B2C: solo practitioner, teacher, retail customer, hobbyist)
   - "IRRELEVANT" (unrelated industry, spam, false positive)

2. Assign a Priority Tier:
   - "Tier 1 - High Priority" (High-volume wholesale importers, distributors, chain studios)
   - "Tier 2 - Medium Priority" (Independent studios, spas, sound therapists, specialty shops)
   - "Tier 3 - Low Priority" (Individual buyers, solo hobbyists)
   - "Irrelevant / Unqualified" (Irrelevant industries, spam)

3. Compute an Intent Score from 0 to 100 based on B2B purchase volume potential for singing bowls.
4. Recommend a tailored outreach angle / product pitch (under 20 words).
5. State a concise reasoning (under 25 words).

Respond ONLY with valid JSON in this exact structure:
{{
  "category": "BUSINESS",
  "tier": "Tier 1 - High Priority",
  "intent_score": 85,
  "confidence": 0.95,
  "outreach_angle": "Tailored product pitch",
  "reasoning": "Concise justification"
}}
"""


def parse_gemini_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Robustly parse a JSON dictionary from Gemini's response text.

    Handles raw JSON, markdown-wrapped JSON (```json ... ```), and embedded JSON.

    Args:
        raw_text: Raw text string returned by the model.

    Returns:
        Parsed dictionary if valid, None otherwise.
    """
    if not raw_text or not isinstance(raw_text, str):
        return None

    cleaned = raw_text.strip()

    # Strip markdown code blocks if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Fallback regex search for JSON object inside prose
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return None


# ==============================================================================
# HEURISTIC & MOCK CLASSIFIERS
# ==============================================================================
def heuristic_classify_lead(buyer: Dict[str, str]) -> LeadClassification:
    """Classify lead using expert domain heuristics for Singing Bowls export.

    Args:
        buyer: Normalized buyer dictionary.

    Returns:
        LeadClassification object.
    """
    company = (buyer.get("company_name") or "").strip().lower()
    email = (buyer.get("email") or "").strip().lower()
    website = (buyer.get("website") or "").strip().lower()

    email_domain = email.split("@")[-1] if "@" in email else ""
    is_freemail = email_domain in FREEMAIL_DOMAINS

    # 1. Check for negative / irrelevant keywords
    all_text = f"{company} {email_domain} {website}".lower()
    for irr in IRRELEVANT_KEYWORDS:
        if irr in all_text:
            return LeadClassification(
                category=CATEGORY_IRRELEVANT,
                tier=TIER_IRRELEVANT,
                intent_score=15,
                confidence=0.88,
                outreach_angle="N/A - Unqualified industry lead.",
                reasoning=f"Identified unrelated commercial sector ({irr}) in lead profile.",
                source="Heuristic",
            )

    # 2. Check for Wholesale / Importer / Distributor (Tier 1)
    matched_wholesale = [
        kw for kw in WHOLESALE_KEYWORDS
        if re.search(r"\b" + re.escape(kw) + r"\b", company)
    ]
    if company and matched_wholesale:
        return LeadClassification(
            category=CATEGORY_BUSINESS,
            tier=TIER_1,
            intent_score=94,
            confidence=0.95,
            outreach_angle="Direct Himalayan Export: Artisan Hand-Hammered 7-Metals Singing Bowls with Wholesale Volume Pricing.",
            reasoning=f"High-volume wholesale importer/distributor indicators: {', '.join(matched_wholesale[:2])}.",
            source="Heuristic",
        )

    # 3. Check for dedicated corporate wholesale domain
    if not is_freemail and email_domain and ("wholesale" in email_domain or "impex" in email_domain or "distributor" in email_domain):
        return LeadClassification(
            category=CATEGORY_BUSINESS,
            tier=TIER_1,
            intent_score=92,
            confidence=0.92,
            outreach_angle="Wholesale Master-Grade Singing Bowls and Gongs with Custom Etching for Corporate Importers.",
            reasoning=f"Commercial wholesale domain (@{email_domain}).",
            source="Heuristic",
        )

    # 4. Check for Studio / Wellness / Spa / Meditation (Tier 2)
    matched_wellness = [kw for kw in STUDIO_WELLNESS_KEYWORDS if kw in company or kw in website]
    matched_corp = [kw for kw in CORPORATE_SUFFIXES if kw in company]
    if company and (matched_wellness or matched_corp or not is_freemail):
        return LeadClassification(
            category=CATEGORY_BUSINESS,
            tier=TIER_2,
            intent_score=80,
            confidence=0.88,
            outreach_angle="Master-Grade 7-Chakra Tuned Singing Bowl Sets tailored for sound baths and therapy sessions.",
            reasoning=f"Active studio/spa commercial entity ('{buyer.get('company_name')}').",
            source="Heuristic",
        )

    # 5. Check for Individual / Solo Practitioner (Tier 3)
    if is_freemail or not company:
        return LeadClassification(
            category=CATEGORY_INDIVIDUAL,
            tier=TIER_3,
            intent_score=45,
            confidence=0.82,
            outreach_angle="Handcrafted Himalayan Singing Bowl Starter Kits with Felt Mallet & Brocade Cushion for Personal Practice.",
            reasoning=f"Individual practitioner or consumer profile operating via personal email (@{email_domain or 'consumer'}).",
            source="Heuristic",
        )

    # Fallback default
    return LeadClassification(
        category=CATEGORY_INDIVIDUAL,
        tier=TIER_3,
        intent_score=50,
        confidence=0.70,
        outreach_angle="Himalayan Singing Bowls & Acoustic Accessories Catalog.",
        reasoning="Sparse commercial details; defaulted to entry-tier inquiry.",
        source="Heuristic",
    )


def mock_gemini_classify(buyer: Dict[str, str]) -> LeadClassification:
    """Deterministic, domain-aware mock AI classifier for offline testing in TEST_MODE.

    Simulates the reasoning and output structure of Google Gemini AI with high fidelity.

    Args:
        buyer: Normalized buyer dictionary.

    Returns:
        LeadClassification object with source='Gemini AI (Mock)'.
    """
    base = heuristic_classify_lead(buyer)
    # Refine mock AI output to simulate Gemini's style
    ai_reasoning = f"[Gemini AI] Evaluated {buyer.get('company_name') or buyer.get('buyer_name') or 'lead'}: {base.reasoning}"
    return LeadClassification(
        category=base.category,
        tier=base.tier,
        intent_score=base.intent_score,
        confidence=base.confidence,
        outreach_angle=base.outreach_angle,
        reasoning=ai_reasoning,
        source="Gemini AI (Mock)",
    )


# ==============================================================================
# LIVE GEMINI API INTERACTION
# ==============================================================================
def call_gemini_api(prompt: str, api_key: str) -> Optional[str]:
    """Call Google Gemini API using google.genai SDK or REST fallback.

    Args:
        prompt: Evaluation prompt text.
        api_key: Valid Google Gemini API key.

    Returns:
        Generated text string or None on failure.
    """
    # 1. Try modern google.genai SDK
    if GENAI_SDK_AVAILABLE:
        try:
            client = genai.Client(api_key=api_key)
            config_obj = types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            )
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=config_obj,
            )
            if response and response.text:
                return response.text
        except Exception:
            pass

    # 2. Secondary fallback: direct REST API via urllib
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


# ==============================================================================
# UNIFIED CLASSIFICATION INTERFACES
# ==============================================================================
def classify_lead(
    buyer: Dict[str, str],
    use_ai: bool = True,
    test_mode: Optional[bool] = None,
) -> LeadClassification:
    """Primary classification interface for Phase 3.

    Evaluates a buyer lead using Gemini AI (or mock simulation in TEST_MODE),
    with automatic graceful fallback to domain heuristics.

    Args:
        buyer: Normalized buyer dictionary.
        use_ai: If True, attempts Gemini AI classification.
        test_mode: Explicit test mode toggle; defaults to config.TEST_MODE.

    Returns:
        LeadClassification object containing category, tier, score, angle, and reasoning.
    """
    is_test = config.TEST_MODE if test_mode is None else test_mode
    api_key = (config.GEMINI_API_KEY or "").strip()

    # In TEST_MODE, or if no valid API key is present, use offline mock/heuristic
    if is_test or not api_key or api_key.startswith("your_"):
        if use_ai:
            return mock_gemini_classify(buyer)
        return heuristic_classify_lead(buyer)

    # Live Mode with configured Gemini API Key
    if use_ai:
        prompt = build_classification_prompt(buyer)
        raw_response = call_gemini_api(prompt, api_key)
        if raw_response:
            parsed = parse_gemini_json(raw_response)
            if parsed:
                cat = str(parsed.get("category", CATEGORY_INDIVIDUAL)).strip().upper()
                if cat not in (CATEGORY_BUSINESS, CATEGORY_INDIVIDUAL, CATEGORY_IRRELEVANT):
                    cat = CATEGORY_INDIVIDUAL

                tier = str(parsed.get("tier", TIER_3)).strip()
                if tier not in (TIER_1, TIER_2, TIER_3, TIER_IRRELEVANT):
                    tier = TIER_2 if cat == CATEGORY_BUSINESS else TIER_3

                score = int(parsed.get("intent_score", 70))
                confidence = float(parsed.get("confidence", 0.90))
                angle = str(parsed.get("outreach_angle", "Handcrafted Singing Bowls Catalog.")).strip()
                reasoning = str(parsed.get("reasoning", "Classified via Gemini AI.")).strip()

                return LeadClassification(
                    category=cat,
                    tier=tier,
                    intent_score=score,
                    confidence=confidence,
                    outreach_angle=angle,
                    reasoning=f"[Gemini AI] {reasoning}",
                    source="Gemini AI",
                )

    # Fallback to Heuristic if live call failed
    heuristic_res = heuristic_classify_lead(buyer)
    heuristic_res.source = "Heuristic (Fallback)"
    return heuristic_res


def batch_classify(
    buyers: List[Dict[str, str]],
    use_ai: bool = True,
    test_mode: Optional[bool] = None,
) -> Tuple[List[Tuple[Dict[str, str], LeadClassification]], ClassificationStatistics]:
    """Classify a batch of buyer leads and aggregate statistics.

    Args:
        buyers: List of normalized buyer dictionaries.
        use_ai: If True, uses Gemini AI or mock AI.
        test_mode: Optional test mode override.

    Returns:
        Tuple of (list of (buyer, classification) pairs, ClassificationStatistics).
    """
    results: List[Tuple[Dict[str, str], LeadClassification]] = []
    stats = ClassificationStatistics()

    for buyer in buyers:
        classification = classify_lead(buyer, use_ai=use_ai, test_mode=test_mode)
        results.append((buyer, classification))
        stats.record(classification)

    return results, stats


# ==============================================================================
# BACKWARD COMPATIBILITY INTERFACES (FOR PHASE 1 & 2 TESTS)
# ==============================================================================
def heuristic_classify(buyer: Dict[str, str]) -> Tuple[str, str, float]:
    """Legacy interface returning (category, reasoning, confidence)."""
    result = heuristic_classify_lead(buyer)
    return result.category, result.reasoning, result.confidence


def gemini_classify(buyer: Dict[str, str], api_key: str) -> Optional[Tuple[str, str, float]]:
    """Legacy interface returning (category, reasoning, confidence) or None."""
    prompt = build_classification_prompt(buyer)
    raw = call_gemini_api(prompt, api_key)
    if not raw:
        return None
    parsed = parse_gemini_json(raw)
    if not parsed:
        return None
    cat = parsed.get("category", CATEGORY_INDIVIDUAL).upper()
    reasoning = parsed.get("reasoning", "Classified via Gemini AI.")
    conf = float(parsed.get("confidence", 0.9))
    return cat, f"[Gemini AI] {reasoning}", conf


def classify_buyer(buyer: Dict[str, str]) -> Tuple[str, str, float]:
    """Legacy interface returning (category, reasoning, confidence)."""
    result = classify_lead(buyer)
    return result.category, result.reasoning, result.confidence
