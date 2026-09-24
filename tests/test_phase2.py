"""Unit tests for Phase 2: Lead Discovery + Data Quality.

Tests:
1. Google Search Adapter (TEST_MODE offline behavior & schema adherence)
2. Directory Search Adapter (BeautifulSoup HTML parsing & extraction)
3. Website Search Adapter (Regex email extraction & HTML contact parsing)
4. Unified Discovery Interface (discover_all_leads in search package)
5. Data Quality Assessment (VALID, INCOMPLETE, INVALID_EMAIL, DUPLICATE, REJECTED)
6. Deduplication logic (Email matching & Company + Website matching)
7. Discovery Statistics Tracker (Metric aggregation and reporting)
"""

import tempfile
import unittest
from pathlib import Path

from extraction.data_extractor import (
    buyer_company_and_website_exists,
    init_buyers_csv,
    normalize_buyer,
)
from search.directory_search import parse_directory_html, search_directory
from search.google_search import search_google
from search.website_search import (
    extract_contacts_from_html,
    extract_emails_from_text,
    search_website,
)
from search import discover_all_leads
from validation.data_quality import (
    STATUS_DUPLICATE,
    STATUS_INCOMPLETE,
    STATUS_INVALID_EMAIL,
    STATUS_REJECTED,
    STATUS_VALID,
    DiscoveryStatistics,
    assess_lead_quality,
)

STANDARD_KEYS = {
    "buyer_name",
    "company_name",
    "email",
    "website",
    "country",
    "source_platform",
}


class TestGoogleSearchAdapter(unittest.TestCase):
    """Tests for google_search module."""

    def test_google_search_test_mode(self):
        """Should return standardized lead dictionaries without making network calls."""
        leads = search_google(limit=3, test_mode=True)
        self.assertGreater(len(leads), 0)
        self.assertLessEqual(len(leads), 3)

        for lead in leads:
            self.assertTrue(STANDARD_KEYS.issubset(lead.keys()))
            self.assertEqual(lead["source_platform"], "Google Search")


class TestDirectorySearchAdapter(unittest.TestCase):
    """Tests for directory_search module and BeautifulSoup parsing."""

    def test_parse_directory_html(self):
        """Should parse structured directory cards from raw HTML."""
        html = """
        <div class="directory-list">
            <article class="directory-card">
                <h3 class="company-name">Himalayan Bowls Wholesaler Ltd</h3>
                <p class="contact-person">Tenzing Norgay</p>
                <span class="email-address">wholesale@himalayanbowls.org</span>
                <a class="website-link" href="https://himalayanbowls.org">Visit</a>
                <span class="country-badge">Nepal</span>
            </article>
        </div>
        """
        extracted = parse_directory_html(html, source_label="Custom Directory")
        self.assertEqual(len(extracted), 1)
        lead = extracted[0]
        self.assertEqual(lead["company_name"], "Himalayan Bowls Wholesaler Ltd")
        self.assertEqual(lead["buyer_name"], "Tenzing Norgay")
        self.assertEqual(lead["email"], "wholesale@himalayanbowls.org")
        self.assertEqual(lead["website"], "https://himalayanbowls.org")
        self.assertEqual(lead["country"], "Nepal")
        self.assertEqual(lead["source_platform"], "Custom Directory")

    def test_search_directory_test_mode(self):
        """Should load bundled sample directory leads in test mode."""
        leads = search_directory(limit=4, test_mode=True)
        self.assertGreater(len(leads), 0)
        for lead in leads:
            self.assertTrue(STANDARD_KEYS.issubset(lead.keys()))


class TestWebsiteSearchAdapter(unittest.TestCase):
    """Tests for website contact and text email extraction."""

    def test_extract_emails_from_text(self):
        """Should find valid emails in text and filter invalid/noise formats."""
        text = """
        For bulk orders contact info@zenithbowls.com or support@zenithbowls.com.
        Do not send to banner.png or invalid-email.
        Direct questions to ceo@himalaya.co.uk!
        """
        emails = extract_emails_from_text(text)
        self.assertIn("info@zenithbowls.com", emails)
        self.assertIn("support@zenithbowls.com", emails)
        self.assertIn("ceo@himalaya.co.uk", emails)
        self.assertNotIn("banner.png", emails)

    def test_extract_contacts_from_html(self):
        """Should extract contacts with title and country from page HTML."""
        html = """
        <html>
            <head><title>Zenith Sound Spa - Contact</title></head>
            <body>
                <h1>Zenith Sound Spa</h1>
                <p>Located in Toronto, Canada</p>
                <p>Email: sales@zenithspa.ca</p>
            </body>
        </html>
        """
        leads = extract_contacts_from_html(html, source_url="https://zenithspa.ca")
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["company_name"], "Zenith Sound Spa")
        self.assertEqual(leads[0]["email"], "sales@zenithspa.ca")
        self.assertEqual(leads[0]["country"], "Canada")
        self.assertEqual(leads[0]["website"], "https://zenithspa.ca")


class TestUnifiedDiscovery(unittest.TestCase):
    """Tests for aggregated discover_all_leads interface."""

    def test_discover_all_leads_aggregation(self):
        """Should aggregate leads across Google, Directories, and Websites."""
        leads = discover_all_leads(limit=10, test_mode=True)
        self.assertGreater(len(leads), 0)
        sources = {l["source_platform"] for l in leads}
        self.assertTrue(len(sources) >= 2)


class TestDataQualityAssessment(unittest.TestCase):
    """Tests for data hygiene, quality classification, and status reporting."""

    def setUp(self):
        self.existing_buyers = [
            {
                "buyer_name": "Maya Lin",
                "company_name": "Sound Sanctuary Studio",
                "email": "contact@soundsanctuary.com",
                "website": "https://www.soundsanctuary.com",
                "country": "USA",
                "source_platform": "Google Search",
            }
        ]

    def test_status_valid(self):
        """A complete, fresh record with valid email should return STATUS_VALID."""
        lead = {
            "buyer_name": "Elena Weber",
            "company_name": "Klang Studio GmbH",
            "email": "orders@klangstudio.de",
            "website": "https://klangstudio.de",
            "country": "Germany",
            "source_platform": "EU Directory",
        }
        status, reason = assess_lead_quality(lead, self.existing_buyers)
        self.assertEqual(status, STATUS_VALID)

    def test_status_incomplete(self):
        """Valid email but missing metadata fields should return STATUS_INCOMPLETE."""
        lead = {
            "buyer_name": "John Smith",
            "company_name": "",  # Missing company
            "email": "johnsmith@gmail.com",
            "website": "",  # Missing website
            "country": "USA",
            "source_platform": "Web",
        }
        status, reason = assess_lead_quality(lead, self.existing_buyers)
        self.assertEqual(status, STATUS_INCOMPLETE)
        self.assertIn("company_name", reason)

    def test_status_invalid_email(self):
        """Malformed email syntax should return STATUS_INVALID_EMAIL."""
        lead = {
            "buyer_name": "Bad Contact",
            "company_name": "Bad Co",
            "email": "not-an-email",
            "website": "https://bad.com",
            "country": "USA",
            "source_platform": "Directory",
        }
        status, reason = assess_lead_quality(lead, self.existing_buyers)
        self.assertEqual(status, STATUS_INVALID_EMAIL)

    def test_status_rejected_missing_email(self):
        """Missing email address should return STATUS_REJECTED."""
        lead = {
            "buyer_name": "No Email Buyer",
            "company_name": "Silent Co",
            "email": "",
            "website": "https://silent.com",
            "country": "UK",
            "source_platform": "Web",
        }
        status, reason = assess_lead_quality(lead, self.existing_buyers)
        self.assertEqual(status, STATUS_REJECTED)

    def test_status_rejected_placeholder_email(self):
        """Placeholder or dummy email addresses should return STATUS_REJECTED."""
        lead = {
            "buyer_name": "Dummy Tester",
            "company_name": "Test LLC",
            "email": "test@test.com",
            "website": "https://test.com",
            "country": "USA",
            "source_platform": "Web",
        }
        status, reason = assess_lead_quality(lead, self.existing_buyers)
        self.assertEqual(status, STATUS_REJECTED)

    def test_status_duplicate_email(self):
        """Email already in existing database should return STATUS_DUPLICATE."""
        duplicate_lead = {
            "buyer_name": "Maya Lin Duplicate",
            "company_name": "Sound Sanctuary Studio",
            "email": "CONTACT@SOUNDSANCTUARY.COM",  # Case-insensitive duplicate
            "website": "https://www.soundsanctuary.com",
            "country": "USA",
            "source_platform": "Directory",
        }
        status, reason = assess_lead_quality(duplicate_lead, self.existing_buyers)
        self.assertEqual(status, STATUS_DUPLICATE)

    def test_status_duplicate_company_and_website(self):
        """Duplicate company name and website with different email should return STATUS_DUPLICATE."""
        lead = {
            "buyer_name": "Another Contact",
            "company_name": "Sound Sanctuary Studio",  # Matches existing
            "email": "other@soundsanctuary.com",
            "website": "https://www.soundsanctuary.com",  # Matches existing
            "country": "USA",
            "source_platform": "Web",
        }
        status, reason = assess_lead_quality(lead, self.existing_buyers)
        self.assertEqual(status, STATUS_DUPLICATE)


class TestDiscoveryStatistics(unittest.TestCase):
    """Tests for discovery metrics tracker."""

    def test_metrics_recording(self):
        """Should accurately aggregate counts across all categories."""
        stats = DiscoveryStatistics()
        stats.record_lead(STATUS_VALID, is_newly_saved=True)
        stats.record_lead(STATUS_INCOMPLETE, is_newly_saved=True)
        stats.record_lead(STATUS_INVALID_EMAIL, is_newly_saved=False)
        stats.record_lead(STATUS_DUPLICATE, is_newly_saved=False)
        stats.record_lead(STATUS_REJECTED, is_newly_saved=False)

        data = stats.to_dict()
        self.assertEqual(data["raw_results"], 5)
        self.assertEqual(data["valid_leads"], 1)
        self.assertEqual(data["incomplete_leads"], 1)
        self.assertEqual(data["invalid_leads"], 2)  # 1 invalid + 1 rejected
        self.assertEqual(data["duplicates"], 1)
        self.assertEqual(data["new_leads"], 2)


if __name__ == "__main__":
    unittest.main()
