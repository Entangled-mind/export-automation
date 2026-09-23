"""Unit tests for Phase 2: Buyer Discovery and AI Classification."""

import tempfile
import unittest
from pathlib import Path

from classification.classifier import (
    classify_buyer,
    heuristic_classify,
)
from discovery.search_adapter import (
    discover_buyers,
    parse_directory_html,
)
from extraction.data_extractor import (
    add_classified_buyer,
    read_classified_buyers,
)


class TestSearchAdapter(unittest.TestCase):
    """Tests for discovery and search adapter functionality."""

    def test_discover_buyers_structure(self):
        """Discovered leads must contain all standardized buyer dictionary keys."""
        leads = discover_buyers(query="Singing Bowls", limit=5, use_demo=True)
        self.assertGreater(len(leads), 0)
        required_keys = {
            "buyer_name",
            "company_name",
            "email",
            "website",
            "country",
            "source_platform",
        }
        for lead in leads:
            self.assertTrue(required_keys.issubset(lead.keys()))

    def test_parse_directory_html(self):
        """Should parse buyer cards from HTML snippet."""
        sample_html = """
        <div class="directory">
            <div class="buyer-card">
                <span class="buyer-name">Test Buyer</span>
                <span class="company-name">Test Singing Bowls Ltd</span>
                <span class="buyer-email">test@bowls.com</span>
                <span class="buyer-website">https://bowls.com</span>
                <span class="buyer-country">Nepal</span>
            </div>
        </div>
        """
        extracted = parse_directory_html(sample_html, source_label="Test HTML")
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0]["buyer_name"], "Test Buyer")
        self.assertEqual(extracted[0]["company_name"], "Test Singing Bowls Ltd")
        self.assertEqual(extracted[0]["email"], "test@bowls.com")


class TestAIClassifier(unittest.TestCase):
    """Tests for B2B vs B2C buyer classification."""

    def test_heuristic_classify_business(self):
        """Contacts with commercial terms or corporate domains should be BUSINESS."""
        business_buyer = {
            "buyer_name": "Liam Gallagher",
            "company_name": "Dharma Meditation Wholesalers Ltd",
            "email": "orders@dharmameditation.co.uk",
            "website": "https://www.dharmameditation.co.uk",
            "country": "UK",
        }
        category, reason, confidence = heuristic_classify(business_buyer)
        self.assertEqual(category, "BUSINESS")
        self.assertGreater(confidence, 0.7)
        self.assertIn("Wholesalers", business_buyer["company_name"])

    def test_heuristic_classify_individual(self):
        """Contacts with freemail and no corporate entity should be INDIVIDUAL."""
        individual_buyer = {
            "buyer_name": "Michael Vance",
            "company_name": "",
            "email": "michael.vance88@gmail.com",
            "website": "",
            "country": "USA",
        }
        category, reason, confidence = heuristic_classify(individual_buyer)
        self.assertEqual(category, "INDIVIDUAL")
        self.assertIn("Personal consumer", reason)

    def test_classify_buyer_fallback(self):
        """classify_buyer must work reliably without an active GEMINI_API_KEY."""
        buyer = {
            "buyer_name": "Klaus Weber",
            "company_name": "Himalayan Art & Sound GmbH",
            "email": "purchasing@himalayan-sound.de",
            "website": "https://www.himalayan-sound.de",
            "country": "Germany",
        }
        category, reason, confidence = classify_buyer(buyer)
        self.assertIn(category, ("BUSINESS", "INDIVIDUAL"))
        self.assertGreater(confidence, 0.5)


class TestClassifiedStorage(unittest.TestCase):
    """Tests for saving and querying segregated CSVs."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_csv = Path(self.test_dir.name) / "test_business_buyers.csv"

    def tearDown(self):
        self.test_dir.cleanup()

    def test_add_and_read_classified_buyer(self):
        """Should save buyer with classification and reason to the target file."""
        buyer = {
            "buyer_name": "Ananya Sharma",
            "company_name": "Lotus Sound Importers",
            "email": "ananya@lotussound.in",
            "website": "https://lotussound.in",
            "country": "India",
            "source_platform": "Search",
        }
        success, msg = add_classified_buyer(
            buyer,
            classification="BUSINESS",
            reasoning="Import company keyword",
            custom_path=self.test_csv,
        )
        self.assertTrue(success)

        rows = read_classified_buyers(category="BUSINESS", custom_path=self.test_csv)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["email"], "ananya@lotussound.in")
        self.assertEqual(rows[0]["classification"], "BUSINESS")
        self.assertEqual(rows[0]["reasoning"], "Import company keyword")

    def test_prevent_duplicate_classified_buyer(self):
        """Should prevent inserting the same email twice into a segregated file."""
        buyer = {
            "buyer_name": "Elena Rostova",
            "company_name": "",
            "email": "elena_yoga@yahoo.com",
            "website": "",
            "country": "Germany",
            "source_platform": "Community",
        }
        success1, _ = add_classified_buyer(
            buyer, "INDIVIDUAL", "Freemail", custom_path=self.test_csv
        )
        self.assertTrue(success1)

        success2, msg2 = add_classified_buyer(
            buyer, "INDIVIDUAL", "Freemail", custom_path=self.test_csv
        )
        self.assertFalse(success2)
        self.assertIn("already exists", msg2)


if __name__ == "__main__":
    unittest.main()
