"""Unit tests for EXPORT Automation System (Phase 1).

Tests core functionality including:
- Email normalization
- Buyer dictionary normalization & handling missing optional fields
- Email syntax validation (valid vs invalid cases)
- Duplicate buyer detection in buyers.csv
- Sent-history duplicate detection in sent_log.csv
- Comprehensive outreach eligibility screening
"""

import tempfile
import unittest
from pathlib import Path

from extraction.data_extractor import (
    add_buyer,
    buyer_email_exists,
    init_buyers_csv,
    normalize_buyer,
    normalize_email,
    read_all_buyers,
)
from logging_module.activity_logger import (
    init_sent_log,
    is_sent_successfully,
    log_sent_entry,
    read_sent_history,
)
from validation.email_validator import (
    check_outreach_eligibility,
    is_valid_email,
)


class TestEmailNormalization(unittest.TestCase):
    """Tests for normalizing email strings."""

    def test_whitespace_and_lowercase(self):
        """Should trim leading/trailing spaces and convert to lowercase."""
        self.assertEqual(
            normalize_email("   John@Example.COM   "), "john@example.com"
        )
        self.assertEqual(normalize_email("Jane.Doe@XYZ.ORG"), "jane.doe@xyz.org")

    def test_empty_and_none_handling(self):
        """Should safely handle None and empty strings without crashing."""
        self.assertEqual(normalize_email(""), "")
        self.assertEqual(normalize_email(None), "")
        self.assertEqual(normalize_email("   "), "")


class TestBuyerNormalization(unittest.TestCase):
    """Tests for normalizing raw buyer dictionary records."""

    def test_complete_record_cleaning(self):
        """Should strip whitespace from all fields and normalize email."""
        raw = {
            "buyer_name": " John Smith ",
            "company_name": " ABC Imports ",
            "email": " JOHN@EXAMPLE.COM ",
            "website": " https://example.com/ ",
            "country": " USA ",
            "source_platform": " Google ",
        }
        normalized = normalize_buyer(raw)
        self.assertEqual(normalized["buyer_name"], "John Smith")
        self.assertEqual(normalized["company_name"], "ABC Imports")
        self.assertEqual(normalized["email"], "john@example.com")
        self.assertEqual(normalized["website"], "https://example.com/")
        self.assertEqual(normalized["country"], "USA")
        self.assertEqual(normalized["source_platform"], "Google")

    def test_missing_optional_fields(self):
        """Should safely supply default empty strings when fields are missing."""
        raw = {
            "buyer_name": "Lone Buyer",
            "email": "lone@example.com",
        }
        normalized = normalize_buyer(raw)
        self.assertEqual(normalized["buyer_name"], "Lone Buyer")
        self.assertEqual(normalized["email"], "lone@example.com")
        self.assertEqual(normalized["company_name"], "")
        self.assertEqual(normalized["website"], "")
        self.assertEqual(normalized["country"], "")
        self.assertEqual(normalized["source_platform"], "")


class TestEmailValidation(unittest.TestCase):
    """Tests for email syntax and basic format validation."""

    def test_valid_emails(self):
        """Standard valid email formats should pass validation."""
        valid_cases = [
            "john@gmail.com",
            "sales@company.com",
            "info@example.co.uk",
            "buyer.contact+tag@singingbowls.de",
        ]
        for email in valid_cases:
            with self.subTest(email=email):
                self.assertTrue(is_valid_email(email))

    def test_invalid_emails(self):
        """Syntactically broken or placeholder emails must fail validation."""
        invalid_cases = [
            "",
            "abc",
            "abc@",
            "@gmail.com",
            "test",
            "example@example",
            "john @gmail.com",
            "invalid-email",
            "user@domain@domain.com",
            "user@-domain.com",
            None,
        ]
        for email in invalid_cases:
            with self.subTest(email=email):
                self.assertFalse(is_valid_email(email))


class TestDuplicateBuyerDetection(unittest.TestCase):
    """Tests for duplicate detection in buyers.csv."""

    def setUp(self):
        """Create a temporary directory for isolated file operations."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.test_dir.name) / "test_buyers.csv"

    def tearDown(self):
        """Clean up temporary directory after tests."""
        self.test_dir.cleanup()

    def test_prevent_case_insensitive_duplicate(self):
        """Adding a buyer with the same email in different cases should be rejected."""
        init_buyers_csv(self.csv_path)

        first_buyer = {
            "buyer_name": "Original John",
            "company_name": "First Co",
            "email": "john@example.com",
            "website": "",
            "country": "USA",
            "source_platform": "Google",
        }
        success1, msg1 = add_buyer(first_buyer, self.csv_path)
        self.assertTrue(success1)
        self.assertIn("added successfully", msg1)

        # Attempt to add with uppercase email
        duplicate_buyer = {
            "buyer_name": "Duplicate John",
            "company_name": "Another Co",
            "email": "JOHN@EXAMPLE.COM",
            "website": "",
            "country": "USA",
            "source_platform": "Website",
        }
        success2, msg2 = add_buyer(duplicate_buyer, self.csv_path)
        self.assertFalse(success2)
        self.assertIn("Duplicate skipped", msg2)

        # Check only 1 row was stored
        buyers = read_all_buyers(self.csv_path)
        self.assertEqual(len(buyers), 1)
        self.assertEqual(buyers[0]["email"], "john@example.com")


class TestSentHistoryDetection(unittest.TestCase):
    """Tests for tracking and checking outreach history in sent_log.csv."""

    def setUp(self):
        """Create a temporary directory for isolated sent_log operations."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.test_dir.name) / "test_sent_log.csv"

    def tearDown(self):
        """Clean up temporary directory."""
        self.test_dir.cleanup()

    def test_sent_history_lookup(self):
        """Should identify SUCCESS entries case-insensitively and ignore FAILED entries."""
        init_sent_log(self.csv_path)

        # Log a successful outreach
        log_sent_entry("success_buyer@example.com", "SUCCESS", self.csv_path)

        # Log a failed attempt
        log_sent_entry("failed_buyer@example.com", "FAILED", self.csv_path)

        # Check lookup
        self.assertTrue(
            is_sent_successfully("SUCCESS_BUYER@EXAMPLE.COM", self.csv_path)
        )
        self.assertFalse(
            is_sent_successfully("failed_buyer@example.com", self.csv_path)
        )
        self.assertFalse(
            is_sent_successfully("uncontacted@example.com", self.csv_path)
        )


class TestOutreachEligibilityFlow(unittest.TestCase):
    """Tests for the combined eligibility workflow."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.buyers_path = Path(self.test_dir.name) / "buyers.csv"
        self.sent_path = Path(self.test_dir.name) / "sent_log.csv"
        init_buyers_csv(self.buyers_path)
        init_sent_log(self.sent_path)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_screening_logic(self):
        """Test rejection, previously-sent skipping, duplicate skipping, and approval."""
        # 1. Invalid syntax
        status1, _ = check_outreach_eligibility(
            "invalid-syntax", self.buyers_path, self.sent_path
        )
        self.assertEqual(status1, "REJECTED_INVALID")

        # 2. Previously sent
        log_sent_entry("sent@example.com", "SUCCESS", self.sent_path)
        status2, _ = check_outreach_eligibility(
            "SENT@EXAMPLE.COM", self.buyers_path, self.sent_path
        )
        self.assertEqual(status2, "SKIPPED_PREVIOUSLY_SENT")

        # 3. Duplicate in buyers
        add_buyer({"email": "existing@example.com", "buyer_name": "Bob"}, self.buyers_path)
        status3, _ = check_outreach_eligibility(
            "EXISTING@EXAMPLE.COM", self.buyers_path, self.sent_path
        )
        self.assertEqual(status3, "SKIPPED_DUPLICATE_BUYER")

        # 4. Fresh eligible contact
        status4, _ = check_outreach_eligibility(
            "fresh@example.com", self.buyers_path, self.sent_path
        )
        self.assertEqual(status4, "ELIGIBLE")


if __name__ == "__main__":
    unittest.main()
