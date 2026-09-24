"""Unit tests for Phase 3: AI Lead Classification.

Tests:
1. Singing Bowls domain heuristic classification (Tier 1 Wholesalers, Tier 2 Studios, Tier 3 Solo, Irrelevant).
2. Gemini AI prompt generation and JSON response parsing (including markdown fences and raw text).
3. Mock Gemini AI classifier execution in TEST_MODE.
4. Graceful fallback on API error or missing credentials.
5. Segregated CSV storage with Phase 3 fields (tier, intent_score, outreach_angle).
6. ClassificationStatistics tracker aggregation.
7. Backward compatibility for legacy Phase 1/2 classification interfaces.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from classification import (
    CATEGORY_BUSINESS,
    CATEGORY_INDIVIDUAL,
    CATEGORY_IRRELEVANT,
    TIER_1,
    TIER_2,
    TIER_3,
    TIER_IRRELEVANT,
    ClassificationStatistics,
    LeadClassification,
    batch_classify,
    build_classification_prompt,
    classify_buyer,
    classify_lead,
    gemini_classify,
    heuristic_classify,
    heuristic_classify_lead,
    mock_gemini_classify,
    parse_gemini_json,
)
from extraction.data_extractor import (
    add_classified_buyer,
    init_classified_csv,
    read_classified_buyers,
)


class TestSingingBowlsHeuristics(unittest.TestCase):
    """Tests domain-specific heuristic classification for Singing Bowls export."""

    def test_tier_1_wholesale_importer(self):
        """Wholesale distributors and importers should classify as Tier 1 Business."""
        lead = {
            "buyer_name": "Klaus Weber",
            "company_name": "Himalayan Art & Sound GmbH Wholesalers",
            "email": "purchasing@himalayan-sound.de",
            "website": "https://www.himalayan-sound.de",
            "country": "Germany",
            "source_platform": "EU Business Directory",
        }
        res = heuristic_classify_lead(lead)
        self.assertEqual(res.category, CATEGORY_BUSINESS)
        self.assertEqual(res.tier, TIER_1)
        self.assertGreaterEqual(res.intent_score, 85)
        self.assertIn("Himalayan", res.outreach_angle)

    def test_tier_2_studio_spa(self):
        """Sound healing studios, spas, and yoga academies should classify as Tier 2 Business."""
        lead = {
            "buyer_name": "Chloe Tremblay",
            "company_name": "Zenith Wellness & Spa Supplies",
            "email": "procurement@zenithspa.ca",
            "website": "https://zenithspa.ca",
            "country": "Canada",
            "source_platform": "Spa Directory",
        }
        res = heuristic_classify_lead(lead)
        self.assertEqual(res.category, CATEGORY_BUSINESS)
        self.assertEqual(res.tier, TIER_2)
        self.assertGreaterEqual(res.intent_score, 70)
        self.assertIn("7-Chakra", res.outreach_angle)

    def test_tier_3_solo_practitioner(self):
        """Individual practitioners using freemail without company should classify as Tier 3 Individual."""
        lead = {
            "buyer_name": "Michael Vance",
            "company_name": "",
            "email": "michael.vance88@gmail.com",
            "website": "",
            "country": "USA",
            "source_platform": "Sound Healing Forum",
        }
        res = heuristic_classify_lead(lead)
        self.assertEqual(res.category, CATEGORY_INDIVIDUAL)
        self.assertEqual(res.tier, TIER_3)
        self.assertLessEqual(res.intent_score, 65)

    def test_irrelevant_industry_filter(self):
        """Leads in unrelated industries (crypto, plumbing, logistics) should be tagged IRRELEVANT."""
        lead = {
            "buyer_name": "Bob Builder",
            "company_name": "Apex Construction & Plumbing LLC",
            "email": "bob@apexconstruction.com",
            "website": "https://apexconstruction.com",
            "country": "USA",
            "source_platform": "Directory",
        }
        res = heuristic_classify_lead(lead)
        self.assertEqual(res.category, CATEGORY_IRRELEVANT)
        self.assertEqual(res.tier, TIER_IRRELEVANT)
        self.assertLessEqual(res.intent_score, 25)


class TestGeminiPromptAndParsing(unittest.TestCase):
    """Tests prompt generation and robust JSON parsing."""

    def test_prompt_construction(self):
        """Prompt should include contact details, products, and JSON specifications."""
        lead = {
            "buyer_name": "Sarah Connor",
            "company_name": "Skynet Wellness Inc",
            "email": "sarah@wellness-singingbowls.com",
            "website": "https://wellness-singingbowls.com",
            "country": "Australia",
            "source_platform": "Directory",
        }
        prompt = build_classification_prompt(lead)
        self.assertIn("Sarah Connor", prompt)
        self.assertIn("Skynet Wellness Inc", prompt)
        self.assertIn("Singing Bowls", prompt)
        self.assertIn('"category"', prompt)
        self.assertIn('"tier"', prompt)

    def test_parse_clean_json(self):
        """Should parse well-formatted JSON responses."""
        raw = json.dumps({
            "category": "BUSINESS",
            "tier": "Tier 1 - High Priority",
            "intent_score": 90,
            "confidence": 0.95,
            "outreach_angle": "Wholesale Tibetan Bowls",
            "reasoning": "Large European distributor",
        })
        parsed = parse_gemini_json(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get("category"), "BUSINESS")
        self.assertEqual(parsed.get("tier"), "Tier 1 - High Priority")

    def test_parse_markdown_wrapped_json(self):
        """Should strip markdown code fences from Gemini responses."""
        raw = """```json
        {
            "category": "BUSINESS",
            "tier": "Tier 2 - Medium Priority",
            "intent_score": 80,
            "confidence": 0.90,
            "outreach_angle": "Studio Bowl Sets",
            "reasoning": "Yoga retreat center"
        }
        ```"""
        parsed = parse_gemini_json(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get("tier"), "Tier 2 - Medium Priority")

    def test_parse_corrupt_text(self):
        """Malformed text should return None without throwing exceptions."""
        self.assertIsNone(parse_gemini_json("This is not JSON at all."))
        self.assertIsNone(parse_gemini_json(""))
        self.assertIsNone(parse_gemini_json(None))


class TestMockAndOfflineClassification(unittest.TestCase):
    """Tests offline mock AI behavior in TEST_MODE."""

    def test_mock_gemini_classify(self):
        """Mock Gemini classifier should return realistic AI-style reasoning."""
        lead = {
            "buyer_name": "David Miller",
            "company_name": "Apex Meditation Gear",
            "email": "sales@apexmeditation.com",
            "website": "https://apexmeditation.com",
            "country": "Australia",
            "source_platform": "Web Search",
        }
        result = mock_gemini_classify(lead)
        self.assertIsInstance(result, LeadClassification)
        self.assertEqual(result.source, "Gemini AI (Mock)")
        self.assertIn("[Gemini AI]", result.reasoning)
        self.assertEqual(result.category, CATEGORY_BUSINESS)

    def test_classify_lead_in_test_mode(self):
        """classify_lead with test_mode=True should run mock AI deterministically."""
        lead = {
            "buyer_name": "Ananya Sharma",
            "company_name": "Lotus Sound Healing Importers",
            "email": "ananya@lotussound.in",
            "website": "https://lotussound.in",
            "country": "India",
            "source_platform": "Google Search",
        }
        result = classify_lead(lead, use_ai=True, test_mode=True)
        self.assertEqual(result.source, "Gemini AI (Mock)")
        self.assertEqual(result.tier, TIER_1)


class TestClassificationFallback(unittest.TestCase):
    """Tests resilience when external API calls fail."""

    @patch("classification.classifier.call_gemini_api")
    def test_graceful_fallback_when_api_fails(self, mock_call):
        """When Gemini API returns None or errors, system falls back to Heuristics."""
        mock_call.return_value = None

        lead = {
            "buyer_name": "Liam Gallagher",
            "company_name": "Dharma Meditation Wholesalers",
            "email": "orders@dharmameditation.co.uk",
            "website": "https://www.dharmameditation.co.uk",
            "country": "UK",
            "source_platform": "Wholesale Trade Portal",
        }
        # In live mode (test_mode=False) with mock failure
        with patch("config.GEMINI_API_KEY", "dummy_live_key"):
            result = classify_lead(lead, use_ai=True, test_mode=False)
            self.assertEqual(result.source, "Heuristic (Fallback)")
            self.assertEqual(result.tier, TIER_1)
            self.assertEqual(result.category, CATEGORY_BUSINESS)


class TestSegregatedStorage(unittest.TestCase):
    """Tests saving classified leads into business and individual CSV files."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.business_csv = Path(self.test_dir.name) / "test_business.csv"
        self.individual_csv = Path(self.test_dir.name) / "test_individual.csv"

    def tearDown(self):
        self.test_dir.cleanup()

    def test_add_and_read_classified_business(self):
        """Should save business buyer with tier, intent_score, and outreach_angle."""
        lead = {
            "buyer_name": "Marcus Vance",
            "company_name": "Alpine Sound Healing GmbH",
            "email": "wholesale@alpinesound.de",
            "website": "https://alpinesound.de",
            "country": "Germany",
            "source_platform": "Directory",
        }
        success, msg = add_classified_buyer(
            buyer_data=lead,
            classification=CATEGORY_BUSINESS,
            reasoning="Major German sound studio wholesale client",
            custom_path=self.business_csv,
            tier=TIER_1,
            intent_score=95,
            outreach_angle="Wholesale Bulk Tibetan Bowls",
        )
        self.assertTrue(success)
        self.assertIn("Saved", msg)

        # Read back
        records = read_classified_buyers(CATEGORY_BUSINESS, custom_path=self.business_csv)
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["email"], "wholesale@alpinesound.de")
        self.assertEqual(rec["classification"], CATEGORY_BUSINESS)
        self.assertEqual(rec["tier"], TIER_1)
        self.assertEqual(rec["intent_score"], "95")
        self.assertEqual(rec["outreach_angle"], "Wholesale Bulk Tibetan Bowls")

    def test_classified_duplicate_prevention(self):
        """Should reject re-adding identical email to classified CSV."""
        lead = {
            "buyer_name": "John",
            "email": "unique@example.com",
            "company_name": "Unique Co",
        }
        s1, _ = add_classified_buyer(lead, "BUSINESS", custom_path=self.business_csv)
        self.assertTrue(s1)

        s2, msg2 = add_classified_buyer(lead, "BUSINESS", custom_path=self.business_csv)
        self.assertFalse(s2)
        self.assertIn("already exists", msg2)


class TestClassificationStatistics(unittest.TestCase):
    """Tests metrics aggregation in ClassificationStatistics."""

    def test_statistics_aggregation(self):
        stats = ClassificationStatistics()

        res1 = LeadClassification(
            category=CATEGORY_BUSINESS,
            tier=TIER_1,
            intent_score=95,
            confidence=0.95,
            outreach_angle="Angle 1",
            reasoning="Reason 1",
            source="Gemini AI (Mock)",
        )
        res2 = LeadClassification(
            category=CATEGORY_INDIVIDUAL,
            tier=TIER_3,
            intent_score=40,
            confidence=0.85,
            outreach_angle="Angle 2",
            reasoning="Reason 2",
            source="Heuristic",
        )
        stats.record(res1)
        stats.record(res2)

        summary = stats.summary()
        self.assertEqual(summary["total_evaluated"], 2)
        self.assertEqual(summary["business_count"], 1)
        self.assertEqual(summary["individual_count"], 1)
        self.assertEqual(summary["tier_1_count"], 1)
        self.assertEqual(summary["tier_3_count"], 1)
        self.assertEqual(summary["ai_count"], 1)
        self.assertEqual(summary["heuristic_count"], 1)


class TestLegacyCompatibility(unittest.TestCase):
    """Verifies that legacy Phase 1 & 2 interfaces remain intact."""

    def test_legacy_heuristic_classify(self):
        lead = {"company_name": "ABC Wholesalers", "email": "info@abc.com"}
        cat, reason, conf = heuristic_classify(lead)
        self.assertEqual(cat, "BUSINESS")
        self.assertIsInstance(reason, str)
        self.assertIsInstance(conf, float)

    def test_legacy_classify_buyer(self):
        lead = {"company_name": "", "email": "test@gmail.com"}
        cat, reason, conf = classify_buyer(lead)
        self.assertEqual(cat, "INDIVIDUAL")
        self.assertIsInstance(reason, str)
        self.assertIsInstance(conf, float)


if __name__ == "__main__":
    unittest.main()
