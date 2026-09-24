"""Unit tests for Phase 4: Outreach & Email Automation.

Tests:
1. Template rendering & personalized placeholder fallbacks (Tier 1, 2, 3).
2. MIME message builder with PDF catalog attachment.
3. Rate limiter tracking against DAILY_SEND_LIMIT.
4. Duplicate outreach prevention against sent_log.csv.
5. Email syntax screening before dispatch.
6. Safe simulation / dry-run dispatch in TEST_MODE.
7. SMTP exception handling and failure logging.
8. Batch outreach execution and OutreachStatistics aggregation.
"""

from email.mime.multipart import MIMEMultipart
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import config
from logging_module.activity_logger import init_sent_log, log_sent_entry
from outreach import (
    DEFAULT_TIER1_ANGLE,
    DEFAULT_TIER2_ANGLE,
    DEFAULT_TIER3_ANGLE,
    EmailDraft,
    OutreachResult,
    OutreachStatistics,
    build_mime_message,
    can_send_today,
    get_personalized_placeholders,
    get_today_sent_count,
    render_email_draft,
    send_batch_outreach,
    send_single_email,
)


class TestTemplatePersonalization(unittest.TestCase):
    """Tests template manager and placeholder rendering."""

    def test_tier_1_wholesale_placeholders(self):
        """Tier 1 templates should incorporate wholesale details and buyer info."""
        buyer = {
            "buyer_name": "Klaus Weber",
            "company_name": "Himalayan Sound GmbH",
            "country": "Germany",
            "email": "purchasing@himalayan-sound.de",
            "tier": config.TIER_1,
            "outreach_angle": "Wholesale Bulk Container Tibetan Bowls",
        }
        draft = render_email_draft(buyer)
        self.assertEqual(draft.to_email, "purchasing@himalayan-sound.de")
        self.assertIn("Himalayan Sound GmbH", draft.subject)
        self.assertIn("Klaus Weber", draft.body_text)
        self.assertIn("Wholesale Bulk Container Tibetan Bowls", draft.body_text)
        self.assertIn("<html>", draft.body_html.lower())

    def test_tier_2_studio_placeholders(self):
        """Tier 2 templates should focus on studio and chakra sound bath sets."""
        buyer = {
            "buyer_name": "Maya Lin",
            "company_name": "Sound Sanctuary Studio",
            "country": "USA",
            "email": "contact@soundsanctuary.com",
            "tier": config.TIER_2,
        }
        draft = render_email_draft(buyer)
        self.assertIn("7-Chakra", draft.subject)
        self.assertIn("Maya Lin", draft.body_text)
        self.assertIn("Sound Sanctuary Studio", draft.body_text)

    def test_missing_fields_fallback(self):
        """Missing buyer name, company, or country should fall back gracefully."""
        buyer = {
            "email": "solo@example.com",
            "buyer_name": "",
            "company_name": "",
            "country": "",
        }
        draft = render_email_draft(buyer, tier=config.TIER_2)
        self.assertIn("Purchasing Team", draft.body_text)
        self.assertIn("your esteemed organization", draft.body_text)
        self.assertNotIn("None", draft.body_text)
        self.assertNotIn("None", draft.subject)


class TestMimeMessageBuilder(unittest.TestCase):
    """Tests construction of RFC-compliant MIME multipart messages."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.pdf_path = Path(self.test_dir.name) / "test_presentation.pdf"
        with open(self.pdf_path, "wb") as f:
            f.write(b"%PDF-1.4 Mock PDF content")

    def tearDown(self):
        self.test_dir.cleanup()

    def test_mime_structure_with_attachment(self):
        """MIME message should have mixed content with alternative body and application/pdf."""
        draft = EmailDraft(
            to_email="partner@example.com",
            to_name="Jane Doe",
            company_name="Apex Spas",
            subject="Exclusive Sound Bowls Catalog",
            body_text="Plain text version.",
            body_html="<p>HTML version.</p>",
            attachment_path=self.pdf_path,
        )
        msg = build_mime_message(draft, sender_email="sender@singingbowls.com", sender_name="Guild Lead")
        self.assertIsInstance(msg, MIMEMultipart)
        self.assertIn("partner@example.com", msg["To"])
        self.assertIn("sender@singingbowls.com", msg["From"])
        self.assertEqual(msg["Subject"], "Exclusive Sound Bowls Catalog")

        # Verify payload contains text/html and application/pdf
        payload_types = [part.get_content_type() for part in msg.walk()]
        self.assertIn("text/plain", payload_types)
        self.assertIn("text/html", payload_types)
        self.assertIn("application/pdf", payload_types)

    def test_mime_without_attachment(self):
        """Should assemble cleanly without errors when attachment is absent."""
        draft = EmailDraft(
            to_email="partner@example.com",
            to_name="Jane Doe",
            company_name="Apex Spas",
            subject="Exclusive Sound Bowls Catalog",
            body_text="Plain text version.",
            body_html="<p>HTML version.</p>",
            attachment_path=None,
        )
        msg = build_mime_message(draft)
        payload_types = [part.get_content_type() for part in msg.walk()]
        self.assertIn("text/plain", payload_types)
        self.assertIn("text/html", payload_types)
        self.assertNotIn("application/pdf", payload_types)


class TestRateLimiter(unittest.TestCase):
    """Tests daily dispatch limit tracking."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.sent_log = Path(self.test_dir.name) / "sent_log.csv"
        init_sent_log(self.sent_log)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_daily_limit_enforcement(self):
        """System should detect when daily limit is exhausted."""
        # Log 2 dispatches
        log_sent_entry("a@example.com", "SUCCESS", self.sent_log)
        log_sent_entry("b@example.com", "SIMULATED_SUCCESS", self.sent_log)

        self.assertEqual(get_today_sent_count(self.sent_log), 2)

        can_send_1, curr_1, max_1 = can_send_today(limit=5, sent_log_path=self.sent_log)
        self.assertTrue(can_send_1)
        self.assertEqual(curr_1, 2)

        can_send_2, curr_2, max_2 = can_send_today(limit=2, sent_log_path=self.sent_log)
        self.assertFalse(can_send_2)
        self.assertEqual(curr_2, 2)


class TestSingleEmailOutreach(unittest.TestCase):
    """Tests single email dispatch flow in simulation mode."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.sent_log = Path(self.test_dir.name) / "sent_log.csv"
        self.activity_log = Path(self.test_dir.name) / "activity_log.csv"
        init_sent_log(self.sent_log)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_invalid_email_syntax_rejected(self):
        """Broken emails should be flagged REJECTED_INVALID_EMAIL."""
        buyer = {"email": "not-an-email", "buyer_name": "Bob"}
        result = send_single_email(
            buyer, test_mode=True, sent_log_path=self.sent_log, activity_log_path=self.activity_log
        )
        self.assertEqual(result.status, "REJECTED_INVALID_EMAIL")

    def test_duplicate_outreach_suppressed(self):
        """Previously contacted email should be SKIPPED_PREVIOUSLY_SENT."""
        log_sent_entry("contacted@example.com", "SUCCESS", self.sent_log)

        buyer = {"email": "contacted@example.com", "buyer_name": "Bob"}
        result = send_single_email(
            buyer, test_mode=True, sent_log_path=self.sent_log, activity_log_path=self.activity_log
        )
        self.assertEqual(result.status, "SKIPPED_PREVIOUSLY_SENT")

    def test_simulated_dispatch_in_test_mode(self):
        """In TEST_MODE, email is recorded as SIMULATED_SUCCESS without network requests."""
        buyer = {
            "email": "fresh@example.com",
            "buyer_name": "Fresh Buyer",
            "company_name": "Fresh Studio",
            "tier": config.TIER_2,
        }
        result = send_single_email(
            buyer, test_mode=True, dry_run=True, sent_log_path=self.sent_log, activity_log_path=self.activity_log
        )
        self.assertEqual(result.status, "SIMULATED_SUCCESS")
        self.assertIn("Fresh Studio", result.subject)

        # Confirm recorded in sent_log
        self.assertEqual(get_today_sent_count(self.sent_log), 1)


class TestLiveSmtpDispatch(unittest.TestCase):
    """Tests live SMTP transmission and error handling via mock."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.sent_log = Path(self.test_dir.name) / "sent_log.csv"
        self.activity_log = Path(self.test_dir.name) / "activity_log.csv"
        init_sent_log(self.sent_log)

    def tearDown(self):
        self.test_dir.cleanup()

    @patch("smtplib.SMTP_SSL")
    def test_smtp_success(self, mock_smtp):
        """Successful SMTP session records SUCCESS."""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        buyer = {
            "email": "real@example.com",
            "buyer_name": "Real Client",
            "company_name": "Sound Spa",
            "tier": config.TIER_1,
        }

        with patch("config.GMAIL_EMAIL", "test@gmail.com"):
            with patch("config.GMAIL_APP_PASSWORD", "app_pass"):
                with patch("config.USE_SSL", True):
                    result = send_single_email(
                        buyer,
                        dry_run=False,
                        test_mode=False,
                        sent_log_path=self.sent_log,
                        activity_log_path=self.activity_log,
                    )
                    self.assertEqual(result.status, "SUCCESS")
                    mock_server.sendmail.assert_called_once()
                    mock_server.quit.assert_called_once()

    @patch("smtplib.SMTP_SSL")
    def test_smtp_failure_handling(self, mock_smtp):
        """SMTP error records FAILED and logs error cleanly."""
        mock_smtp.side_effect = Exception("Authentication failed 535")

        buyer = {
            "email": "fail@example.com",
            "buyer_name": "Fail Client",
            "company_name": "Spa Inc",
            "tier": config.TIER_1,
        }

        with patch("config.GMAIL_EMAIL", "test@gmail.com"):
            with patch("config.GMAIL_APP_PASSWORD", "wrong_pass"):
                with patch("config.USE_SSL", True):
                    result = send_single_email(
                        buyer,
                        dry_run=False,
                        test_mode=False,
                        sent_log_path=self.sent_log,
                        activity_log_path=self.activity_log,
                    )
                    self.assertEqual(result.status, "FAILED")
                    self.assertIn("Authentication failed", result.message)


class TestBatchOutreach(unittest.TestCase):
    """Tests batch campaign execution across qualified leads."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.sent_log = Path(self.test_dir.name) / "sent_log.csv"
        self.activity_log = Path(self.test_dir.name) / "activity_log.csv"
        init_sent_log(self.sent_log)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_batch_filtering_and_statistics(self):
        """Batch should only process targeted tiers and track stats."""
        buyers = [
            {"email": "b1@example.com", "tier": config.TIER_1, "company_name": "C1"},
            {"email": "b2@example.com", "tier": config.TIER_2, "company_name": "C2"},
            {"email": "b3@example.com", "tier": config.TIER_3, "company_name": "C3"},  # excluded
        ]

        results, stats = send_batch_outreach(
            buyers=buyers,
            target_tiers=[config.TIER_1, config.TIER_2],
            test_mode=True,
            dry_run=True,
            sent_log_path=self.sent_log,
            activity_log_path=self.activity_log,
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(stats.simulated_count, 2)
        self.assertEqual(stats.total_targeted, 2)


if __name__ == "__main__":
    unittest.main()
