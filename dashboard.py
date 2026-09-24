"""Interactive Web Dashboard for EXPORT Automation System (Phase 6: Web Dashboard & UI).

Features:
- Enterprise SQLite Backend: Direct real-time queries against export_automation.db with CSV fallback.
- Live Executive KPI Cards: Total Buyers, B2B Wholesalers (Tier 1), Studios (Tier 2), Solo (Tier 3), Outreach Dispatches, Daily Limits.
- Interactive Pipeline Execution: Trigger end-to-end pipeline run from UI with live result reporting.
- Real-time Email Validator Playground: Instant regex syntax validation and duplicate screening.
- Live AI Lead Classification Playground: Interactive evaluation returning Category, Tier, Intent Score, and Pitch Angle.
- Manual Lead Addition Modal: Instant normalization, validation, deduplication, and dual SQLite/CSV persistence.
- Filterable & Searchable Data Tables: Master Leads, B2B Wholesale Leads, B2C Solo Buyers, Sent History, and Audit Logs.
- One-Click Data Exports: Export buyers.csv, business_buyers.csv, sent_log.csv, and SQLite DB.
- Demo Reset Engine: One-click reset and re-seed for clean portfolio demonstration video recordings.
"""

import csv
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse

from classification import (
    CATEGORY_BUSINESS,
    CATEGORY_INDIVIDUAL,
    TIER_1,
    TIER_2,
    TIER_3,
    classify_buyer,
    classify_lead,
)
import config
from database import (
    get_activity_logs,
    get_all_buyers,
    get_all_classifications,
    get_buyer_by_email,
    get_database_stats,
    get_outreach_history,
    init_database,
    is_email_contacted,
    migrate_csv_to_sqlite,
    record_activity,
    save_classification,
    upsert_buyer,
)
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
from outreach import (
    can_send_today,
    get_today_sent_count,
    send_batch_outreach,
    send_single_email,
)
from validation.email_validator import is_valid_email

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "dashboard.html"


def get_dashboard_stats() -> Dict[str, Any]:
    """Compile summary metrics directly from the SQLite database with CSV fallback.

    Returns:
        Dictionary containing counts, priority tier breakdowns, countries, and sources.
    """
    try:
        init_database()
        db_stats = get_database_stats()
        all_buyers = get_all_buyers()
        can_send, sent_today, max_limit = can_send_today()

        country_counts: Dict[str, int] = {}
        source_counts: Dict[str, int] = {}
        for buyer in all_buyers:
            c = buyer.get("country") or "Global / Other"
            country_counts[c] = country_counts.get(c, 0) + 1
            s = buyer.get("source_platform") or "Direct Discovery"
            source_counts[s] = source_counts.get(s, 0) + 1

        recent_acts = get_activity_logs(limit=15)

        return {
            "total_buyers": db_stats["total_buyers"],
            "b2b_buyers": db_stats["business_buyers"],
            "b2c_buyers": db_stats["individual_buyers"],
            "tier_1_count": db_stats["tier_1_count"],
            "tier_2_count": db_stats["tier_2_count"],
            "tier_3_count": db_stats["tier_3_count"],
            "sent_count": db_stats["outreach_success"] + db_stats["outreach_simulated"],
            "activity_count": db_stats["total_activities"],
            "daily_sent": sent_today,
            "daily_limit": max_limit,
            "countries": country_counts,
            "sources": source_counts,
            "recent_activities": recent_acts,
        }
    except Exception:
        # Fallback to CSV files
        all_buyers = read_all_buyers()
        b2b_buyers = read_classified_buyers("BUSINESS")
        b2c_buyers = read_classified_buyers("INDIVIDUAL")
        sent_history = read_sent_history()

        country_counts = {}
        source_counts = {}
        for buyer in all_buyers:
            c = buyer.get("country") or "Global / Other"
            country_counts[c] = country_counts.get(c, 0) + 1
            s = buyer.get("source_platform") or "Direct Discovery"
            source_counts[s] = source_counts.get(s, 0) + 1

        return {
            "total_buyers": len(all_buyers),
            "b2b_buyers": len(b2b_buyers),
            "b2c_buyers": len(b2c_buyers),
            "tier_1_count": sum(1 for b in b2b_buyers if config.TIER_1 in b.get("tier", "")),
            "tier_2_count": sum(1 for b in b2b_buyers if config.TIER_2 in b.get("tier", "")),
            "tier_3_count": len(b2c_buyers),
            "sent_count": len(sent_history),
            "activity_count": 0,
            "daily_sent": len(sent_history),
            "daily_limit": config.DAILY_SEND_LIMIT,
            "countries": country_counts,
            "sources": source_counts,
            "recent_activities": [],
        }


def reset_demo_environment() -> None:
    """Reset and re-seed the test databases so presenter can re-record clean demos."""
    # Remove CSV files
    for p in [config.BUYERS_CSV, config.BUSINESS_BUYERS_CSV, config.INDIVIDUAL_BUYERS_CSV, config.SENT_LOG_CSV, config.ACTIVITY_LOG_CSV]:
        if p.exists():
            p.unlink()

    # Re-initialize clean CSVs
    init_buyers_csv()
    init_classified_csv(config.BUSINESS_BUYERS_CSV)
    init_classified_csv(config.INDIVIDUAL_BUYERS_CSV)
    init_sent_log()
    init_activity_log()

    # Re-initialize clean SQLite DB
    if config.DB_PATH.exists():
        try:
            config.DB_PATH.unlink()
        except Exception:
            pass

    init_database()

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

        elif parsed.path in ("/api/data", "/api/stats"):
            stats = get_dashboard_stats()

            # Query from SQLite with fallback to CSV
            try:
                master = get_all_buyers()
                classified = get_all_classifications()
                b2b = [c for c in classified if c.get("category") == "BUSINESS"]
                b2c = [c for c in classified if c.get("category") == "INDIVIDUAL"]
                sent_log = get_outreach_history(limit=100)
                activities = get_activity_logs(limit=100)
            except Exception:
                master = read_all_buyers()
                b2b = read_classified_buyers("BUSINESS")
                b2c = read_classified_buyers("INDIVIDUAL")
                classified = b2b + b2c
                sent_log = read_sent_history()
                activities = []

            self.send_json({
                "stats": stats,
                "master": master,
                "classified": classified,
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
                mime_type = "application/x-sqlite3" if filename.endswith(".db") else "text/csv"
                self.send_header("Content-Type", mime_type)
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
            # Execute Phase 5 full pipeline
            disc_stats, class_stats, outreach_stats, db_stats = main.run_pipeline()
            self.send_json({
                "status": "success",
                "message": "Full 5-phase export pipeline executed successfully!",
                "discovery": disc_stats.to_dict() if hasattr(disc_stats, "to_dict") else {},
                "classification": class_stats.summary(),
                "outreach": outreach_stats.summary(),
                "database": db_stats,
            })

        elif parsed.path == "/api/test-email":
            body = self.read_json_body()
            email = body.get("email", "")
            valid = is_valid_email(email)
            duplicate = buyer_email_exists(email) or (get_buyer_by_email(email) is not None)
            already_sent = is_sent_successfully(email) or is_email_contacted(email)

            if not valid:
                msg = f"'{email}' fails syntactic checks (missing domain, spaces, or placeholder)."
            elif already_sent:
                msg = f"'{email}' is valid, but previously received outreach (sent_log / database)."
            elif duplicate:
                msg = f"'{email}' is valid, but already cataloged in buyers master database."
            else:
                msg = f"'{email}' is valid, fresh, and eligible for outreach!"

            self.send_json({
                "is_valid": valid,
                "is_duplicate": duplicate or already_sent,
                "message": msg,
            })

        elif parsed.path == "/api/test-classify":
            body = self.read_json_body()
            res = classify_lead(body, use_ai=True)
            self.send_json({
                "category": res.category,
                "tier": res.tier,
                "intent_score": res.intent_score,
                "confidence": res.confidence,
                "outreach_angle": res.outreach_angle,
                "reasoning": res.reasoning,
                "source": res.source,
            })

        elif parsed.path == "/api/add-buyer":
            body = self.read_json_body()
            norm = normalize_buyer(body)
            email = norm["email"]

            if not is_valid_email(email):
                self.send_json({"status": "error", "message": f"Invalid email format: '{email}'"})
                return

            if buyer_email_exists(email) or (get_buyer_by_email(email) is not None):
                self.send_json({"status": "error", "message": f"Duplicate buyer '{email}' already in catalog!"})
                return

            # Add to CSV & SQLite master database
            add_buyer(norm)
            upsert_buyer(norm)

            # Classify lead via Phase 3 AI evaluator
            res = classify_lead(norm, use_ai=True)
            add_classified_buyer(
                buyer_data=norm,
                classification=res.category,
                reasoning=res.reasoning,
                tier=res.tier,
                intent_score=res.intent_score,
                outreach_angle=res.outreach_angle,
                overwrite=True,
            )
            save_classification(
                email=email,
                category=res.category,
                tier=res.tier,
                intent_score=res.intent_score,
                confidence=res.confidence,
                outreach_angle=res.outreach_angle,
                reasoning=res.reasoning,
                source=res.source,
            )

            log_activity(
                event="MANUAL_LEAD_ADDED",
                email=email,
                status=res.tier,
                message=f"Added {norm['buyer_name']} ({norm['company_name']}) - {res.reasoning}",
            )

            self.send_json({
                "status": "success",
                "message": f"Successfully added & classified as {res.tier} ({res.category})!",
                "classification": res.category,
                "tier": res.tier,
                "intent_score": res.intent_score,
                "outreach_angle": res.outreach_angle,
            })

        elif parsed.path == "/api/simulate-outreach":
            # Simulate sending to uncontacted B2B buyers
            b2b_list = [c for c in get_all_classifications() if c.get("category") == "BUSINESS"]
            if not b2b_list:
                b2b_list = read_classified_buyers("BUSINESS")

            results, stats = send_batch_outreach(
                buyers=b2b_list[:3],
                target_tiers=[TIER_1, TIER_2],
                dry_run=True,
                test_mode=True,
            )
            self.send_json({
                "status": "success",
                "sent_count": stats.simulated_count,
                "skipped_duplicate": stats.skipped_duplicate,
            })

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
    print("Open this URL in your web browser to explore your verified export leads.")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server.")
        httpd.server_close()


if __name__ == "__main__":
    start_server(5000)
