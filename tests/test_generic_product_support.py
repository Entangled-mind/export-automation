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

    def test_public_search_provider_is_configured(self):
        from search.search_api import SearchAPIAdapter
        adapter = SearchAPIAdapter(provider="public")
        self.assertTrue(adapter.is_configured())

    def test_save_email_credentials_persists_to_file(self):
        import tempfile
        from pathlib import Path
        from outreach.email_sender import save_email_credentials
        import config

        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".env") as tf:
            tf.write("GMAIL_EMAIL=old@gmail.com\nGMAIL_APP_PASSWORD=old_pass\n")
            env_file = Path(tf.name)

        try:
            success = save_email_credentials(
                email="test_export@gmail.com",
                password="abcd efgh ijkl mnop",
                sender_name="Global Manager",
                sender_company="Exporters Ltd",
                env_path=env_file,
            )
            self.assertTrue(success)
            self.assertEqual(config.GMAIL_EMAIL, "test_export@gmail.com")
            self.assertEqual(config.GMAIL_APP_PASSWORD, "abcdefghijklmnop")
            content = env_file.read_text(encoding="utf-8")
            self.assertIn("GMAIL_EMAIL=test_export@gmail.com", content)
            self.assertIn("GMAIL_APP_PASSWORD=abcdefghijklmnop", content)
            self.assertIn("SMTP_PORT=465", content)
            self.assertIn("USE_SSL=True", content)
        finally:
            if env_file.exists():
                env_file.unlink()

    def test_smtp_credentials_rejects_missing_or_placeholder_password(self):
        from outreach.email_sender import test_smtp_credentials

        ok1, msg1 = test_smtp_credentials(email="", password="some_password")
        self.assertFalse(ok1)
        self.assertIn("not provided", msg1)

        ok2, msg2 = test_smtp_credentials(email="test@gmail.com", password="your_16_character_app_password")
        self.assertFalse(ok2)
        self.assertIn("placeholder", msg2.lower())

