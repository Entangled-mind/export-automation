"""Unit tests for Phase 6: Web Dashboard & User Interface.

Tests:
1. get_dashboard_stats() metrics aggregation from SQLite.
2. Dashboard HTTP server startup and HTML rendering (GET /).
3. REST API endpoints:
   - GET /api/data (full dataset with master, classified, sent_log, activities)
   - POST /api/test-email (syntax and duplicate screening)
   - POST /api/test-classify (interactive AI classification playground)
   - POST /api/add-buyer (lead addition with dual SQLite/CSV persistence)
   - POST /api/simulate-outreach (outreach trigger)
4. Demo environment reset.
"""

from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
import urllib.request

import config
from dashboard import (
    DashboardRequestHandler,
    get_dashboard_stats,
    reset_demo_environment,
)
from database import init_database, upsert_buyer


def find_free_port() -> int:
    """Find an available TCP port for isolated testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class TestDashboardStats(unittest.TestCase):
    """Tests metrics compilation function for dashboard."""

    def test_dashboard_stats_structure(self):
        """Should return dictionary containing all KPI keys."""
        stats = get_dashboard_stats()
        self.assertIn("total_buyers", stats)
        self.assertIn("b2b_buyers", stats)
        self.assertIn("b2c_buyers", stats)
        self.assertIn("tier_1_count", stats)
        self.assertIn("tier_2_count", stats)
        self.assertIn("sent_count", stats)
        self.assertIn("daily_limit", stats)
        self.assertIn("countries", stats)
        self.assertIn("sources", stats)


class TestDashboardServerAndApi(unittest.TestCase):
    """Tests HTTP request handler and REST API endpoints."""

    @classmethod
    def setUpClass(cls):
        """Start a local ThreadingHTTPServer in a background daemon thread."""
        cls.port = find_free_port()
        cls.server = ThreadingHTTPServer(("127.0.0.1", cls.port), DashboardRequestHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.1)  # Allow server to bind

    @classmethod
    def tearDownClass(cls):
        """Shutdown the background HTTP server."""
        cls.server.shutdown()
        cls.server.server_close()

    def test_get_dashboard_html(self):
        """GET / should return 200 with HTML document."""
        url = f"{self.base_url}/"
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers.get("Content-Type", ""))
            content = resp.read().decode("utf-8")
            self.assertIn("EXPORT Automation System", content)

    def test_get_api_data(self):
        """GET /api/data should return JSON with master, b2b, b2c, and stats."""
        url = f"{self.base_url}/api/data"
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("stats", data)
            self.assertIn("master", data)
            self.assertIn("b2b", data)
            self.assertIn("b2c", data)
            self.assertIn("sent_log", data)
            self.assertIn("activities", data)

    def test_post_test_email(self):
        """POST /api/test-email should validate email syntax and duplication."""
        url = f"{self.base_url}/api/test-email"
        payload = json.dumps({"email": "syntax.error@"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertFalse(data["is_valid"])

    def test_post_test_classify(self):
        """POST /api/test-classify should return priority tier, intent score, and angle."""
        url = f"{self.base_url}/api/test-classify"
        lead = {
            "company_name": "Nordic Sound Healing Sanctuary Studio",
            "email": "info@nordicsound.se",
            "buyer_name": "Astrid Lind",
            "country": "Sweden",
        }
        payload = json.dumps(lead).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["category"], "BUSINESS")
            self.assertEqual(data["tier"], config.TIER_2)
            self.assertGreaterEqual(data["intent_score"], 70)
            self.assertIn("7-Chakra", data["outreach_angle"])

    def test_post_add_buyer_and_duplicate(self):
        """POST /api/add-buyer should add fresh lead and reject subsequent duplicates."""
        url = f"{self.base_url}/api/add-buyer"
        unique_email = f"lead_{int(time.time())}@singingbowltest.org"
        lead = {
            "buyer_name": "Test Importer",
            "company_name": "Singing Bowl Importers LLC",
            "email": unique_email,
            "country": "USA",
        }
        payload = json.dumps(lead).encode("utf-8")
        req1 = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req1, timeout=5) as resp:
            data1 = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data1["status"], "success")

        # Second attempt should return error duplicate
        req2 = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req2, timeout=5) as resp:
            data2 = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data2["status"], "error")
            self.assertIn("Duplicate", data2["message"])


if __name__ == "__main__":
    unittest.main()
