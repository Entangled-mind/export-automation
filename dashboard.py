"""Interactive Web Dashboard for EXPORT Automation System (Singing Bowls).

Features:
- Live KPI Metrics and Performance Counters
- Interactive Pipeline Stepper & Animation
- Real-time Email Validator Playground (Instant feedback)
- Live AI Classification Playground (B2B vs B2C with confidence)
- Add Manual Lead Modal (with instant normalization and duplicate prevention)
- Filterable & Searchable Data Tables (Master, B2B, B2C, Sent Log, Audit Trail)
- One-click CSV Exports (buyers.csv, business_buyers.csv, sent_log.csv)
- Outreach Simulation Engine (Phase 3 preview with sent_log updates)
- One-click Demo Reset for Video Recording
"""

import csv
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
import urllib.parse

from classification.classifier import classify_buyer
import config
from extraction.data_extractor import (
    BUYER_FIELDS,
    CLASSIFIED_FIELDS,
    add_buyer,
    add_classified_buyer,
    buyer_email_exists,
    init_buyers_csv,
    init_classified_csv,
    normalize_buyer,
    normalize_email,
    read_all_buyers,
    read_classified_buyers,
)
from logging_module.activity_logger import (
    init_activity_log,
    init_sent_log,
    is_sent_successfully,
    log_activity,
    log_sent_entry,
    read_sent_history,
)
import main
from validation.email_validator import is_valid_email

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "dashboard.html"


def get_dashboard_stats() -> Dict[str, Any]:
    """Compile summary metrics from persistent CSV databases."""
    all_buyers = read_all_buyers()
    b2b_buyers = read_classified_buyers("BUSINESS")
    b2c_buyers = read_classified_buyers("INDIVIDUAL")
    sent_history = read_sent_history()

    # Read activity log entries
    activity_entries = []
    if config.ACTIVITY_LOG_CSV.exists():
        with open(config.ACTIVITY_LOG_CSV, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            activity_entries = list(reader)

    # Calculate country counts
    country_counts: Dict[str, int] = {}
    source_counts: Dict[str, int] = {}
    for buyer in all_buyers:
        c = buyer.get("country") or "Global / Other"
        country_counts[c] = country_counts.get(c, 0) + 1
        s = buyer.get("source_platform") or "Direct Discovery"
        source_counts[s] = source_counts.get(s, 0) + 1

    return {
        "total_buyers": len(all_buyers),
        "b2b_buyers": len(b2b_buyers),
        "b2c_buyers": len(b2c_buyers),
        "sent_count": len(sent_history),
        "activity_count": len(activity_entries),
        "countries": country_counts,
        "sources": source_counts,
        "recent_activities": activity_entries[-10:][::-1],
    }


def reset_demo_environment() -> None:
    """Reset and re-seed the test databases so presenter can re-record clean demos."""
    for p in [config.BUYERS_CSV, config.BUSINESS_BUYERS_CSV, config.INDIVIDUAL_BUYERS_CSV, config.SENT_LOG_CSV, config.ACTIVITY_LOG_CSV]:
        if p.exists():
            p.unlink()

    init_buyers_csv()
    init_classified_csv(config.BUSINESS_BUYERS_CSV)
    init_classified_csv(config.INDIVIDUAL_BUYERS_CSV)
    init_sent_log()
    init_activity_log()

    # Seed baseline prior outreach
    log_sent_entry("sarah@wellness-singingbowls.com", "SUCCESS")
    log_activity(
        event="SYSTEM_RESET",
        email="",
        status="INFO",
        message="Demo data reset to clean baseline state for video recording.",
    )


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler providing REST API and serving the dashboard UI."""

    def log_message(self, format: str, *args: Any) -> None:
        """Silence standard console logging for clean CLI output."""
        return

    def send_json(self, data: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        """Helper to return JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def read_json_body(self) -> Dict[str, Any]:
        """Helper to read JSON payload."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw = self.rfile.read(content_length)
            return json.loads(raw.decode("utf-8"))
        return {}

    def do_GET(self) -> None:
        """Handle GET requests for HTML page, JSON API, and file exports."""
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path in ("/", "/dashboard"):
            if not TEMPLATE_PATH.exists():
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Dashboard template missing")
                return

            html_content = TEMPLATE_PATH.read_text(encoding="utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))

        elif parsed.path == "/api/data":
            stats = get_dashboard_stats()
            master = read_all_buyers()
            b2b = read_classified_buyers("BUSINESS")
            b2c = read_classified_buyers("INDIVIDUAL")
            sent_log = read_sent_history()

            activities = []
            if config.ACTIVITY_LOG_CSV.exists():
                with open(config.ACTIVITY_LOG_CSV, mode="r", newline="", encoding="utf-8") as f:
                    activities = list(csv.DictReader(f))[-50:][::-1]

            self.send_json({
                "stats": stats,
                "master": master,
                "b2b": b2b,
                "b2c": b2c,
                "sent_log": sent_log,
                "activities": activities,
            })

        elif parsed.path.startswith("/api/export/"):
            filename = parsed.path.replace("/api/export/", "")
            target_path = config.DATA_DIR / filename
            if target_path.exists():
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition", f"attachment; filename={filename}")
                self.end_headers()
                with open(target_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")

        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def do_POST(self) -> None:
        """Handle POST requests for interactive dashboard actions."""
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/run-pipeline":
            main.run_pipeline()
            self.send_json({"status": "success", "message": "Discovery & Classification pipeline executed successfully!"})

        elif parsed.path == "/api/test-email":
            body = self.read_json_body()
            email = body.get("email", "")
            valid = is_valid_email(email)
            duplicate = buyer_email_exists(email)
            already_sent = is_sent_successfully(email)

            if not valid:
                msg = f"'{email}' fails syntactic checks (missing domain, spaces, or placeholder)."
            elif already_sent:
                msg = f"'{email}' is valid, but previously received outreach (sent_log.csv)."
            elif duplicate:
                msg = f"'{email}' is valid, but already cataloged in buyers.csv."
            else:
                msg = f"'{email}' is valid, fresh, and eligible for outreach!"

            self.send_json({
                "is_valid": valid,
                "is_duplicate": duplicate or already_sent,
                "message": msg,
            })

        elif parsed.path == "/api/test-classify":
            body = self.read_json_body()
            category, reason, confidence = classify_buyer(body)
            self.send_json({
                "category": category,
                "reasoning": reason,
                "confidence": confidence,
            })

        elif parsed.path == "/api/add-buyer":
            body = self.read_json_body()
            norm = normalize_buyer(body)
            email = norm["email"]

            if not is_valid_email(email):
                self.send_json({"status": "error", "message": f"Invalid email format: '{email}'"})
                return

            if buyer_email_exists(email):
                self.send_json({"status": "error", "message": f"Duplicate buyer '{email}' already in catalog!"})
                return

            # Add to master
            add_buyer(norm)

            # Classify
            category, reason, conf = classify_buyer(norm)
            add_classified_buyer(norm, category, reason)

            log_activity(
                event="MANUAL_LEAD_ADDED",
                email=email,
                status=category,
                message=f"Added {norm['buyer_name']} ({norm['company_name']}) - {reason}",
            )

            self.send_json({
                "status": "success",
                "message": f"Successfully added & classified as {category}!",
                "classification": category,
            })

        elif parsed.path == "/api/simulate-outreach":
            # Simulate sending to uncontacted B2B buyers
            b2b_list = read_classified_buyers("BUSINESS")
            sent_count = 0
            for b in b2b_list:
                email = b["email"]
                if not is_sent_successfully(email):
                    log_sent_entry(email, "SUCCESS")
                    log_activity(
                        event="OUTREACH_DISPATCH",
                        email=email,
                        status="SUCCESS",
                        message=f"Dispatched wholesale proposal & PDF catalog to {b.get('company_name') or email}.",
                    )
                    sent_count += 1
                    if sent_count >= 3:
                        break

            self.send_json({"status": "success", "sent_count": sent_count})

        elif parsed.path == "/api/reset-data":
            reset_demo_environment()
            self.send_json({"status": "success", "message": "Demo data reset successfully to clean state."})

        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")


def start_server(port: int = 5000) -> None:
    """Launch the dashboard HTTP server."""
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, DashboardRequestHandler)
    print("=" * 65)
    print(f"EXPORT Automation Dashboard is live at: http://localhost:{port}")
    print("Open this URL in your web browser to explore your Singing Bowls leads.")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server.")
        httpd.server_close()


if __name__ == "__main__":
    start_server(5000)
