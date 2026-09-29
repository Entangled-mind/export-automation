import unittest

from classification.classifier import build_classification_prompt, classify_lead
from search.query_generator import generate_buyer_queries


class TestGenericProductSupport(unittest.TestCase):
    def test_dynamic_query_generation_for_any_product(self):
        queries = generate_buyer_queries(
            product="Organic Coffee",
            country="Germany",
            region="Bavaria",
            buyer_type="Importer",
            additional_context="Premium organic coffee for specialty retail",
        )

        self.assertTrue(any('"Organic Coffee" importer "Germany"'.lower() in q.lower() for q in queries))
        self.assertTrue(any('"Organic Coffee" distributor "Germany"'.lower() in q.lower() for q in queries))
        self.assertTrue(any('"Organic Coffee" exporter'.lower() in q.lower() for q in queries))
        self.assertTrue(any('"Organic Coffee" buyer "Germany"'.lower() in q.lower() for q in queries))

    def test_product_specific_prompt_is_not_singing_bowls_hardcoded(self):
        buyer = {
            "company_name": "SolarTech Trade GmbH",
            "buyer_name": "Anna Mueller",
            "email": "anna@solartrade.de",
            "website": "https://solartrade.de",
            "country": "Germany",
            "source_platform": "Search",
            "product": "Industrial Water Pumps",
        }

        prompt = build_classification_prompt(buyer)
        self.assertIn("Industrial Water Pumps", prompt)
        self.assertNotIn("Singing Bowls", prompt)
        self.assertNotIn("Himalayan", prompt)

    def test_generic_product_classification_uses_product_context(self):
        buyer = {
            "company_name": "SolarTech Trade GmbH",
            "buyer_name": "Anna Mueller",
            "email": "anna@solartrade.de",
            "website": "https://solartrade.de",
            "country": "Germany",
            "source_platform": "Search",
            "product": "Industrial Water Pumps",
        }

        result = classify_lead(buyer, use_ai=False, test_mode=True)
        self.assertIn(result.category, ["BUSINESS", "INDIVIDUAL", "IRRELEVANT"])
        self.assertIn(result.tier, ["Tier 1 - High Priority", "Tier 2 - Medium Priority", "Tier 3 - Low Priority", "Irrelevant / Unqualified"])
