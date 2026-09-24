"""Phase 7 Unit Tests: Production Polish, Configuration, CLI Parsing, and Deployment Validation.

Tests cover:
1. CLI argument parsing for main.py (test/live mode, dry-run/live-send, query, limits, tiers, skip flags).
2. CLI argument parsing for dashboard.py (host, port options).
3. Requirements specification completeness (all Phase 1-7 libraries declared).
4. Environment template completeness (.env.example covers all required settings).
5. Catalog presentation asset availability.
6. Pipeline selective execution with CLI override parameters.
7. Configuration defaults and error handling resilience.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import dashboard
import main


class TestPhase7CLIParsing(unittest.TestCase):
    """Test CLI argument parsing in main.py and dashboard.py."""

    def test_main_parse_args_defaults(self):
        """Test default arguments for main.py."""
        args = main.parse_args([])
        self.assertIsNone(args.test_mode)
        self.assertIsNone(args.dry_run)
        self.assertIsNone(args.query)
        self.assertEqual(args.limit, 15)
        self.assertFalse(args.no_discovery)
        self.assertFalse(args.no_outreach)
        self.assertEqual(args.tier, "1,2")

    def test_main_parse_args_flags(self):
        """Test explicit flags for main.py."""
        args = main.parse_args([
            "--test",
            "--dry-run",
            "--query", "Himalayan Sound Healing Bowls",
            "--limit", "25",
            "--no-discovery",
            "--no-outreach",
            "--tier", "1",
        ])
        self.assertTrue(args.test_mode)
        self.assertTrue(args.dry_run)
        self.assertEqual(args.query, "Himalayan Sound Healing Bowls")
        self.assertEqual(args.limit, 25)
        self.assertTrue(args.no_discovery)
        self.assertTrue(args.no_outreach)
        self.assertEqual(args.tier, "1")

    def test_main_parse_args_live_mode(self):
        """Test live execution flags in main.py."""
        args = main.parse_args(["--live", "--live-send"])
        self.assertFalse(args.test_mode)
        self.assertFalse(args.dry_run)

    def test_dashboard_parse_args_defaults(self):
        """Test default dashboard CLI options."""
        args = dashboard.parse_args([])
        self.assertEqual(args.port, 5000)
        self.assertEqual(args.host, "127.0.0.1")

    def test_dashboard_parse_args_custom(self):
        """Test custom dashboard CLI options."""
        args = dashboard.parse_args(["--port", "8080", "--host", "0.0.0.0"])
        self.assertEqual(args.port, 8080)
        self.assertEqual(args.host, "0.0.0.0")


class TestPhase7ProjectIntegrity(unittest.TestCase):
    """Test repository health, requirements, and environment templates."""

    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent

    def test_requirements_file_has_all_dependencies(self):
        """Verify requirements.txt exists and contains all required packages."""
        req_path = self.root / "requirements.txt"
        self.assertTrue(req_path.exists(), "requirements.txt must exist at project root")

        content = req_path.read_text(encoding="utf-8").lower()
        required_packages = [
            "requests",
            "beautifulsoup4",
            "pandas",
            "python-dotenv",
            "google-genai",
            "reportlab",
        ]
        for pkg in required_packages:
            self.assertIn(pkg, content, f"requirements.txt missing required package: {pkg}")

    def test_env_example_covers_all_configurations(self):
        """Verify .env.example contains all critical environment variable keys."""
        env_example_path = self.root / ".env.example"
        self.assertTrue(env_example_path.exists(), ".env.example must exist at project root")

        content = env_example_path.read_text(encoding="utf-8")
        expected_keys = [
            "TEST_MODE",
            "DRY_RUN",
            "SEARCH_KEYWORD",
            "GEMINI_API_KEY",
            "GEMINI_MODEL",
            "GMAIL_EMAIL",
            "GMAIL_APP_PASSWORD",
            "SMTP_HOST",
            "SMTP_PORT",
            "USE_SSL",
            "DAILY_SEND_LIMIT",
            "PRESENTATION_PATH",
            "SENDER_NAME",
            "SENDER_COMPANY",
            "SENDER_CONTACT",
        ]
        for key in expected_keys:
            self.assertIn(key, content, f".env.example missing configuration parameter: {key}")

    def test_presentation_catalog_asset_exists(self):
        """Verify the company presentation PDF catalog exists."""
        catalog_path = self.root / "assets" / "company_presentation.pdf"
        self.assertTrue(catalog_path.exists(), "assets/company_presentation.pdf must exist")
        self.assertGreater(catalog_path.stat().st_size, 100, "Presentation catalog PDF must not be empty")

    def test_config_paths_and_defaults(self):
        """Verify default configuration attributes exist and are valid types."""
        self.assertTrue(hasattr(config, "DATA_DIR"))
        self.assertTrue(hasattr(config, "DB_PATH"))
        self.assertTrue(hasattr(config, "PRESENTATION_PATH"))
        self.assertIsInstance(config.DAILY_SEND_LIMIT, int)
        self.assertIsInstance(config.TEST_MODE, bool)
        self.assertIsInstance(config.DRY_RUN, bool)


class TestPhase7PipelineSelectiveExecution(unittest.TestCase):
    """Test pipeline run with selective execution flags in temporary sandbox."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_data = Path(self.test_dir) / "data"
        self.test_data.mkdir(parents=True, exist_ok=True)

        self.orig_data_dir = config.DATA_DIR
        self.orig_db_path = config.DB_PATH
        self.orig_buyers_csv = config.BUYERS_CSV
        self.orig_business_csv = config.BUSINESS_BUYERS_CSV
        self.orig_individual_csv = config.INDIVIDUAL_BUYERS_CSV
        self.orig_sent_csv = config.SENT_LOG_CSV
        self.orig_act_csv = config.ACTIVITY_LOG_CSV

        config.DATA_DIR = self.test_data
        config.DB_PATH = self.test_data / "export_automation.db"
        config.BUYERS_CSV = self.test_data / "buyers.csv"
        config.BUSINESS_BUYERS_CSV = self.test_data / "business_buyers.csv"
        config.INDIVIDUAL_BUYERS_CSV = self.test_data / "individual_buyers.csv"
        config.SENT_LOG_CSV = self.test_data / "sent_log.csv"
        config.ACTIVITY_LOG_CSV = self.test_data / "activity_log.csv"

    def tearDown(self):
        config.DATA_DIR = self.orig_data_dir
        config.DB_PATH = self.orig_db_path
        config.BUYERS_CSV = self.orig_buyers_csv
        config.BUSINESS_BUYERS_CSV = self.orig_business_csv
        config.INDIVIDUAL_BUYERS_CSV = self.orig_individual_csv
        config.SENT_LOG_CSV = self.orig_sent_csv
        config.ACTIVITY_LOG_CSV = self.orig_act_csv
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_pipeline_skip_outreach_flag(self):
        """Verify running pipeline with skip_outreach=True executes discovery & classification without outreach."""
        disc_stats, class_stats, outreach_stats, db_stats = main.run_pipeline(
            test_mode=True,
            dry_run=True,
            skip_discovery=False,
            skip_outreach=True,
            limit=5,
        )

        self.assertGreater(disc_stats.raw_results, 0)
        self.assertGreater(class_stats.total_evaluated, 0)
        self.assertEqual(outreach_stats.total_targeted, 0)
        self.assertEqual(outreach_stats.sent_count, 0)
        self.assertEqual(outreach_stats.simulated_count, 0)

    def test_pipeline_skip_discovery_flag(self):
        """Verify running pipeline with skip_discovery=True uses existing leads."""
        # First initialize DB and add a lead
        from database import init_database, upsert_buyer
        init_database()
        upsert_buyer({
            "buyer_name": "Test Existing",
            "company_name": "Sound Sanctuary LLC",
            "email": "existing@soundsanctuary.com",
            "country": "USA",
            "phone": "+1 555 123",
            "website": "https://soundsanctuary.com",
            "source": "Manual",
            "notes": "Existing buyer for test",
        })

        disc_stats, class_stats, outreach_stats, db_stats = main.run_pipeline(
            test_mode=True,
            dry_run=True,
            skip_discovery=True,
            skip_outreach=False,
        )

        self.assertEqual(disc_stats.raw_results, 0)
        self.assertGreater(class_stats.total_evaluated, 0)
        self.assertGreater(db_stats["total_buyers"], 0)


if __name__ == "__main__":
    unittest.main()
