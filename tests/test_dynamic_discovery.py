"""Comprehensive unit tests for Dynamic Real Lead Discovery (Sections 1-14).

Verifies:
1. Buyer query generation (products, countries, quoting, whitespace).
2. Legitimate Search API adapter (TEST_MODE mocks, live mode ConfigurationRequiredError, API mocks).
3. Public website extraction and email regex extraction.
4. Relevance filtering (commercial buyer intent vs non-buyer content).
5. Data quality engine, normalization, placeholder rejection, and validation statuses.
6. Deduplication (by email and company+website).
7. Database schema migration, persistence, and product-filtered queries.
8. End-to-end dynamic lead discovery pipeline.
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import config
from database.connection import db_session
from database.repository import (
    get_all_buyers,
    get_buyer_by_email,
    get_buyers_by_product,
    upsert_buyer,
)
from database.schema import init_database
from search.lead_pipeline import run_discovery_pipeline
from search.query_generator import clean_query_term, generate_buyer_queries
from search.search_api import (
    ConfigurationRequiredError,
    SearchAPIAdapter,
    search_web,
)
from search.website_extractor import (
    check_lead_relevance,
    extract_business_info,
    extract_company_name_from_soup,
    extract_emails_from_text,
    is_placeholder_email,
)
from validation.email_validator import is_valid_email


class TestQueryGenerator(unittest.TestCase):
    """Test suite for buyer query generation across arbitrary products and countries."""

    def test_query_generation_singing_bowls(self):
        queries = generate_buyer_queries("Singing Bowls")
        self.assertGreaterEqual(len(queries), 7)
        self.assertIn('"Singing Bowls" importer', queries)
        self.assertIn('"Singing Bowls" distributor', queries)
        self.assertIn('"Singing Bowls" wholesaler', queries)
        self.assertIn('"Singing Bowls" retailer', queries)
        self.assertIn('"Singing Bowls" buyer', queries)
        self.assertIn('"Singing Bowls" supplier', queries)
        self.assertIn('"Singing Bowls" "contact"', queries)

    def test_query_generation_with_country(self):
        queries = generate_buyer_queries("Yoga Mats", country="USA")
        self.assertGreaterEqual(len(queries), 7)
        self.assertIn('"Yoga Mats" importer "USA"', queries)
        self.assertIn('"Yoga Mats" distributor "USA"', queries)
        self.assertIn('"Yoga Mats" wholesaler "USA"', queries)
        self.assertIn('"Yoga Mats" "contact" "USA"', queries)
        self.assertIn('"Yoga Mats" wholesale "USA"', queries)

    def test_query_generation_other_products(self):
        products = ["Organic Tea", "Handmade Rugs", "Ceramic Mugs", "Pashmina Shawls"]
        for prod in products:
            queries = generate_buyer_queries(prod, country="Germany")
            self.assertTrue(any(f'"{prod}" importer "Germany"' in q for q in queries))

    def test_query_generation_empty_or_whitespace(self):
        self.assertEqual(generate_buyer_queries(""), [])
        self.assertEqual(generate_buyer_queries("   "), [])
        self.assertEqual(generate_buyer_queries(None), [])

    def test_clean_query_term(self):
        self.assertEqual(clean_query_term(' "Yoga Mats" '), "Yoga Mats")
        self.assertEqual(clean_query_term("'Singing Bowls'"), "Singing Bowls")
        self.assertEqual(clean_query_term("   Organic   Tea   "), "Organic Tea")

    def test_run_multi_product_search_aggregates_results(self):
        from search.lead_pipeline import run_multi_product_search

        results = run_multi_product_search(
            products=["Yoga Mats", "Organic Tea"],
            country="USA",
            max_results_per_product=2,
            test_mode=True,
            save_to_db=False,
        )

        self.assertIn("products", results)
        self.assertIn("all_leads", results)
        self.assertGreaterEqual(len(results["products"]), 2)
        self.assertGreaterEqual(len(results["all_leads"]), 1)


class TestSearchAPIAdapter(unittest.TestCase):
    """Test suite for Search API adapter: mocks, test mode, and configuration requirements."""

    def test_test_mode_returns_product_specific_results(self):
        adapter = SearchAPIAdapter()
        results = adapter.search_web(
            query='"Yoga Mats" importer',
            max_results=5,
            test_mode=True,
            product="Yoga Mats",
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("title", results[0])
        self.assertIn("url", results[0])
        self.assertIn("snippet", results[0])
        self.assertFalse(any("example.com" in r["url"] for r in results))
        # Verify product is represented dynamically, not hardcoded to Singing Bowls
        self.assertTrue(any("Yoga Mats" in r["title"] or "yoga-mats" in r["url"] for r in results))

    def test_production_mode_raises_when_unconfigured(self):
        adapter = SearchAPIAdapter(api_key="", engine_id="", serpapi_key="", provider="google")
        with self.assertRaises(ConfigurationRequiredError) as ctx:
            adapter.search_web(query='"Organic Tea" importer', max_results=5, test_mode=False)
        self.assertIn("Search API credentials not configured", str(ctx.exception))

    def test_auto_provider_requires_credentials_for_live_search(self):
        adapter = SearchAPIAdapter(api_key="", engine_id="", serpapi_key="", provider="auto")
        self.assertFalse(adapter.is_configured())
        with self.assertRaises(ConfigurationRequiredError):
            adapter.search_web(
                query='"home decor" wholesale buyers', max_results=5, test_mode=False
            )

    @patch("requests.get")
    def test_google_custom_search_api_mock(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "title": "Zenith Sound Imports - Tibetan Singing Bowls Wholesaler",
                    "link": "https://www.zenithsound.ca/wholesale",
                    "snippet": "Direct commercial importer of authentic hand-beaten singing bowls.",
                }
            ]
        }
        mock_get.return_value = mock_response

        adapter = SearchAPIAdapter(api_key="mock_key", engine_id="mock_cx", provider="google")
        results = adapter.search_web(query="test query", max_results=5, test_mode=False)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Zenith Sound Imports - Tibetan Singing Bowls Wholesaler")
        self.assertEqual(results[0]["url"], "https://www.zenithsound.ca/wholesale")

    @patch("requests.get")
    def test_serpapi_mock(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic_results": [
                {
                    "title": "Himalayan Art & Craft Wholesalers GmbH",
                    "link": "https://www.himalayanart.de/b2b",
                    "snippet": "European distributor for artisan singing bowls and meditation bells.",
                }
            ]
        }
        mock_get.return_value = mock_response

        adapter = SearchAPIAdapter(serpapi_key="mock_serpapi_key", provider="serpapi")
        results = adapter.search_web(query="test query", max_results=5, test_mode=False)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Himalayan Art & Craft Wholesalers GmbH")
        self.assertEqual(results[0]["url"], "https://www.himalayanart.de/b2b")


class TestWebsiteExtractor(unittest.TestCase):
    """Test suite for website extraction, regex email parsing, and relevance filtering."""

    def test_extract_emails_from_text(self):
        sample_text = (
            "Contact our wholesale team at wholesale@zenithspa.ca or procurement@zenithspa.ca. "
            "Do not email image.png or invalid-email! For support: info@zenithspa.ca."
        )
        emails = extract_emails_from_text(sample_text)
        self.assertIn("wholesale@zenithspa.ca", emails)
        self.assertIn("procurement@zenithspa.ca", emails)
        self.assertIn("info@zenithspa.ca", emails)
        self.assertNotIn("image.png", emails)

    def test_is_placeholder_email(self):
        self.assertTrue(is_placeholder_email("user@example.com"))
        self.assertTrue(is_placeholder_email("test@domain.com"))
        self.assertTrue(is_placeholder_email("someone@sample.com"))
        self.assertFalse(is_placeholder_email("orders@himalayansound.de"))
        self.assertFalse(is_placeholder_email("procurement@zenithspa.ca"))

    def test_relevance_filter_positive(self):
        page_text = (
            "Welcome to Alpine Wellness & Sound GmbH. We are a direct wholesale importer and distributor "
            "of premium hand-hammered Singing Bowls and meditation bells across Central Europe."
        )
        is_rel, reason, kws = check_lead_relevance(
            page_text=page_text,
            product_keyword="Singing Bowls",
            title="Alpine Wellness - Singing Bowls Importer",
        )
        self.assertTrue(is_rel)
        self.assertIn("importer", kws)

    def test_relevance_filter_negative(self):
        page_text = (
            "This is a personal blog about cooking organic recipes and baking bread at home. "
            "Follow me on Instagram for daily cooking tips."
        )
        is_rel, reason, kws = check_lead_relevance(
            page_text=page_text,
            product_keyword="Singing Bowls",
            title="My Home Baking Blog",
        )
        self.assertFalse(is_rel)

    def test_unknown_offline_url_does_not_fabricate_lead(self):
        lead = extract_business_info(
            url="https://www.apex-yogamats-supply.example.com/contact-us",
            product_keyword="Yoga Mats",
            search_query='"Yoga Mats" importer "USA"',
            test_mode=True,
        )
        self.assertIsNone(lead)


class TestDatabaseDynamicLeadPersistence(unittest.TestCase):
    """Test suite for SQLite persistence with dynamic lead discovery columns."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_leads.db"
        init_database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_upsert_buyer_with_product_and_source_url(self):
        lead = {
            "buyer_name": "Maya Lin",
            "company_name": "Sound Sanctuary Studio",
            "email": "contact@soundsanctuary.com",
            "website": "https://www.soundsanctuary.com",
            "country": "USA",
            "source_platform": "Public Website Extractor",
            "source_url": "https://www.soundsanctuary.com/wholesale",
            "search_query": '"Singing Bowls" importer "USA"',
            "product": "Singing Bowls",
            "validation_status": config.STATUS_VALID,
        }
        buyer_id = upsert_buyer(lead, db_path=self.db_path)
        self.assertGreater(buyer_id, 0)

        record = get_buyer_by_email("contact@soundsanctuary.com", db_path=self.db_path)
        self.assertIsNotNone(record)
        self.assertEqual(record["product"], "Singing Bowls")
        self.assertEqual(record["source_url"], "https://www.soundsanctuary.com/wholesale")
        self.assertEqual(record["search_query"], '"Singing Bowls" importer "USA"')
        self.assertEqual(record["validation_status"], config.STATUS_VALID)

    def test_get_buyers_by_product_filtering(self):
        # Insert two different products
        lead1 = {
            "company_name": "Yoga Studio One",
            "email": "info@yogastudioone.com",
            "website": "https://yogastudioone.com",
            "product": "Yoga Mats",
            "country": "USA",
        }
        lead2 = {
            "company_name": "Tea Importers Direct",
            "email": "orders@teaimporters.com",
            "website": "https://teaimporters.com",
            "product": "Organic Tea",
            "country": "UK",
        }
        upsert_buyer(lead1, db_path=self.db_path)
        upsert_buyer(lead2, db_path=self.db_path)

        yoga_leads = get_buyers_by_product("Yoga Mats", db_path=self.db_path)
        self.assertEqual(len(yoga_leads), 1)
        self.assertEqual(yoga_leads[0]["company_name"], "Yoga Studio One")

        tea_leads = get_buyers_by_product("Organic Tea", db_path=self.db_path)
        self.assertEqual(len(tea_leads), 1)
        self.assertEqual(tea_leads[0]["company_name"], "Tea Importers Direct")


class TestEndToEndDiscoveryPipeline(unittest.TestCase):
    """Test suite for the full 8-step dynamic lead discovery pipeline."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_pipeline.db"
        init_database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_pipeline_execution_test_mode(self):
        res = run_discovery_pipeline(
            product="Yoga Mats",
            country="USA",
            max_results=5,
            test_mode=True,
            save_to_db=True,
            db_path=self.db_path,
        )

        self.assertEqual(res["product"], "Yoga Mats")
        self.assertEqual(res["country"], "USA")
        self.assertGreater(res["searches_performed"], 0)
        self.assertGreater(res["raw_results_count"], 0)
        self.assertGreater(res["websites_processed"], 0)
        self.assertGreater(res["leads_discovered"], 0)
        self.assertGreater(res["valid_emails"], 0)

        # Verify leads in database
        saved_buyers = get_all_buyers(db_path=self.db_path)
        self.assertGreater(len(saved_buyers), 0)
        self.assertEqual(saved_buyers[0]["product"], "Yoga Mats")

    @patch("search.lead_pipeline.extract_business_info", return_value=None)
    def test_pipeline_keeps_unverified_search_pages_without_inventing_emails(self, _extract):
        adapter = MagicMock()
        adapter.is_configured.return_value = True
        adapter.search_web.return_value = [
            {"title": "Home Decor Wholesale Buyers", "url": "https://buyers.example.org"},
            {"title": "Wholesale Decor Directory", "url": "https://directory.example.org"},
        ]

        result = run_discovery_pipeline(
            product="Home Decor",
            max_results=1,
            test_mode=False,
            save_to_db=False,
            db_path=self.db_path,
            search_adapter=adapter,
        )

        self.assertEqual(len(result["leads"]), 1)
        self.assertEqual(result["leads"][0]["website"], "https://buyers.example.org")
        self.assertEqual(result["leads"][0]["email"], "")
        self.assertTrue(result["leads"][0]["unverified_search_result"])
        self.assertEqual(result["leads"][0]["validation_status"], config.STATUS_INCOMPLETE)

    def test_pipeline_deduplication(self):
        # Run first time
        run_discovery_pipeline(
            product="Organic Tea",
            country="Germany",
            max_results=5,
            test_mode=True,
            save_to_db=True,
            db_path=self.db_path,
        )
        initial_count = len(get_all_buyers(db_path=self.db_path))

        # Run second time with same product
        res2 = run_discovery_pipeline(
            product="Organic Tea",
            country="Germany",
            max_results=5,
            test_mode=True,
            save_to_db=True,
            db_path=self.db_path,
        )
        # Duplicates should have been detected and suppressed
        self.assertGreater(res2["duplicates_removed"], 0)
        final_count = len(get_all_buyers(db_path=self.db_path))
        self.assertEqual(initial_count, final_count)

    def test_pipeline_empty_product_raises_value_error(self):
        with self.assertRaises(ValueError):
            run_discovery_pipeline(product="", test_mode=True, db_path=self.db_path)


if __name__ == "__main__":
    unittest.main()
