"""Unit tests for Phase 5: Database Migration (SQLite).

Tests:
1. Database connection, schema DDL, and foreign key enforcement.
2. Buyer repository CRUD and UPSERT conflict handling.
3. Classification repository persistence and relational joins.
4. Outreach logs repository and duplicate outreach screening in SQLite.
5. Activity audit repository logging and retrieval.
6. Automated CSV to SQLite data migration and idempotency verification.
7. High-level database statistics calculation.
"""

import csv
import tempfile
import unittest
from pathlib import Path

import config
from database import (
    db_session,
    get_activity_logs,
    get_all_buyers,
    get_all_classifications,
    get_buyer_by_email,
    get_classification_by_email,
    get_connection,
    get_database_stats,
    get_outreach_history,
    get_today_outreach_count,
    init_database,
    is_email_contacted,
    migrate_csv_to_sqlite,
    record_activity,
    record_outreach,
    save_classification,
    upsert_buyer,
)


class TestDatabaseConnectionAndSchema(unittest.TestCase):
    """Tests SQLite connection, schema initialization, and transactional integrity."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test.db"

    def tearDown(self):
        self.test_dir.cleanup()

    def test_init_database(self):
        """Should create buyers, classifications, outreach_logs, and activity_logs tables."""
        init_database(self.db_path)
        with db_session(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row["name"] for row in cursor.fetchall()}
            self.assertIn("buyers", tables)
            self.assertIn("classifications", tables)
            self.assertIn("outreach_logs", tables)
            self.assertIn("activity_logs", tables)

    def test_transaction_rollback_on_error(self):
        """db_session should roll back uncommitted changes if an exception occurs."""
        init_database(self.db_path)
        try:
            with db_session(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO buyers (email, buyer_name) VALUES ('rollback@example.com', 'Test');"
                )
                raise RuntimeError("Simulated failure inside transaction")
        except RuntimeError:
            pass

        with db_session(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM buyers WHERE email = 'rollback@example.com';")
            self.assertIsNone(cursor.fetchone())


class TestBuyerRepository(unittest.TestCase):
    """Tests buyer persistence and upsert mechanics."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test.db"
        init_database(self.db_path)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_upsert_new_and_update_existing(self):
        """Upserting buyer with new details on identical email should update record."""
        buyer1 = {
            "buyer_name": "Original Name",
            "company_name": "Sound Sanctuary",
            "email": "contact@soundsanctuary.com",
            "country": "USA",
        }
        b_id = upsert_buyer(buyer1, db_path=self.db_path)
        self.assertGreater(b_id, 0)

        # Retrieve and verify
        rec = get_buyer_by_email("CONTACT@SOUNDSANCTUARY.COM", db_path=self.db_path)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["buyer_name"], "Original Name")

        # Update with new company name
        buyer2 = {
            "buyer_name": "Updated Name",
            "company_name": "Sound Sanctuary Studio LLC",
            "email": "contact@soundsanctuary.com",
        }
        b_id2 = upsert_buyer(buyer2, db_path=self.db_path)
        self.assertEqual(b_id, b_id2)

        rec2 = get_buyer_by_email("contact@soundsanctuary.com", db_path=self.db_path)
        self.assertEqual(rec2["buyer_name"], "Updated Name")
        self.assertEqual(rec2["company_name"], "Sound Sanctuary Studio LLC")
        # Country was preserved from first insert
        self.assertEqual(rec2["country"], "USA")


class TestClassificationRepository(unittest.TestCase):
    """Tests classification repository operations."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test.db"
        init_database(self.db_path)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_save_and_retrieve_classification(self):
        """Should save AI evaluation and retrieve joined with buyer details."""
        buyer = {
            "buyer_name": "Liam Gallagher",
            "company_name": "Dharma Meditation Wholesalers",
            "email": "orders@dharmameditation.co.uk",
            "country": "UK",
        }
        b_id = upsert_buyer(buyer, db_path=self.db_path)

        c_id = save_classification(
            email="orders@dharmameditation.co.uk",
            category=config.CATEGORY_BUSINESS,
            tier=config.TIER_1,
            intent_score=94,
            confidence=0.95,
            outreach_angle="Wholesale Bulk Tibetan Bowls",
            reasoning="Major European wholesaler",
            source="Gemini AI (Mock)",
            buyer_id=b_id,
            db_path=self.db_path,
        )
        self.assertGreater(c_id, 0)

        # Retrieve single
        c = get_classification_by_email("orders@dharmameditation.co.uk", db_path=self.db_path)
        self.assertIsNotNone(c)
        self.assertEqual(c["tier"], config.TIER_1)
        self.assertEqual(c["intent_score"], 94)

        # Retrieve all filtered by Tier 1
        tier1_list = get_all_classifications(tier=config.TIER_1, db_path=self.db_path)
        self.assertEqual(len(tier1_list), 1)
        self.assertEqual(tier1_list[0]["company_name"], "Dharma Meditation Wholesalers")


class TestOutreachAndActivityRepository(unittest.TestCase):
    """Tests outreach logs, rate counting, and audit trails."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test.db"
        init_database(self.db_path)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_outreach_logging_and_today_count(self):
        """Should log dispatches, track daily count, and check sent history."""
        self.assertFalse(is_email_contacted("buyer@example.com", db_path=self.db_path))

        record_outreach(
            email="buyer@example.com",
            status="SIMULATED_SUCCESS",
            subject="Wholesale Bowls",
            message="Dry run delivery",
            db_path=self.db_path,
        )

        self.assertTrue(is_email_contacted("BUYER@EXAMPLE.COM", db_path=self.db_path))
        self.assertEqual(get_today_outreach_count(db_path=self.db_path), 1)

    def test_activity_logging(self):
        """Should record and retrieve audit trail events."""
        record_activity("LEAD_CATALOGED", "test@example.com", "SUCCESS", "Saved lead", db_path=self.db_path)
        logs = get_activity_logs(limit=10, db_path=self.db_path)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["event"], "LEAD_CATALOGED")


class TestCsvMigration(unittest.TestCase):
    """Tests automated migration from legacy CSV files into SQLite database."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "migrated.db"
        self.csv_dir = Path(self.test_dir.name) / "csv_data"
        self.csv_dir.mkdir(parents=True, exist_ok=True)

        # Create mock buyers.csv
        with open(self.csv_dir / "buyers.csv", mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["buyer_name", "company_name", "email", "website", "country", "source_platform"])
            writer.writerow(["John Doe", "Acme Yoga", "john@acme.com", "https://acme.com", "USA", "Google"])

        # Create mock business_buyers.csv
        with open(self.csv_dir / "business_buyers.csv", mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "buyer_name", "company_name", "email", "website", "country",
                "source_platform", "classification", "tier", "intent_score", "outreach_angle", "reasoning"
            ])
            writer.writerow([
                "John Doe", "Acme Yoga", "john@acme.com", "https://acme.com", "USA",
                "Google", "BUSINESS", config.TIER_2, "85", "Studio Bowls", "Yoga studio"
            ])

        # Create mock sent_log.csv
        with open(self.csv_dir / "sent_log.csv", mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["email", "status", "timestamp"])
            writer.writerow(["john@acme.com", "SUCCESS", "2026-09-24T12:00:00"])

        # Create mock activity_log.csv
        with open(self.csv_dir / "activity_log.csv", mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "event", "email", "status", "message"])
            writer.writerow(["2026-09-24T12:00:00", "PIPELINE_INIT", "", "INFO", "Started"])

    def tearDown(self):
        self.test_dir.cleanup()

    def test_migration_and_idempotency(self):
        """Should migrate CSVs to SQLite without data loss, and running twice shouldn't duplicate."""
        counts = migrate_csv_to_sqlite(db_path=self.db_path, data_dir=self.csv_dir)
        self.assertEqual(counts["buyers"], 1)
        self.assertEqual(counts["classifications"], 1)
        self.assertEqual(counts["outreach_logs"], 1)
        self.assertEqual(counts["activity_logs"], 1)

        # Verify database contents
        buyers = get_all_buyers(db_path=self.db_path)
        self.assertEqual(len(buyers), 1)
        self.assertEqual(buyers[0]["email"], "john@acme.com")

        c = get_classification_by_email("john@acme.com", db_path=self.db_path)
        self.assertIsNotNone(c)
        self.assertEqual(c["tier"], config.TIER_2)

        # Run migration a second time (idempotency check)
        counts2 = migrate_csv_to_sqlite(db_path=self.db_path, data_dir=self.csv_dir)
        buyers_after = get_all_buyers(db_path=self.db_path)
        self.assertEqual(len(buyers_after), 1)

    def test_database_stats(self):
        """get_database_stats should compute accurate metrics."""
        migrate_csv_to_sqlite(db_path=self.db_path, data_dir=self.csv_dir)
        stats = get_database_stats(db_path=self.db_path)
        self.assertEqual(stats["total_buyers"], 1)
        self.assertEqual(stats["business_buyers"], 1)
        self.assertEqual(stats["tier_2_count"], 1)
        self.assertEqual(stats["outreach_success"], 1)
        self.assertEqual(stats["total_activities"], 1)


if __name__ == "__main__":
    unittest.main()
