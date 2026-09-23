"""Interactive Web Dashboard for EXPORT Automation System (Singing Bowls).

Serves a modern, responsive web dashboard using Python standard library http.server.
Allows viewing live statistics, B2B/B2C leads, audit logs, and triggering discovery.
"""

import csv
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
import urllib.parse

import config
from extraction.data_extractor import (
    read_all_buyers,
    read_classified_buyers,
)
from logging_module.activity_logger import read_sent_history
import main


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
    for buyer in all_buyers:
        c = buyer.get("country") or "Unspecified"
        country_counts[c] = country_counts.get(c, 0) + 1

    return {
        "total_buyers": len(all_buyers),
        "b2b_buyers": len(b2b_buyers),
        "b2c_buyers": len(b2c_buyers),
        "sent_count": len(sent_history),
        "activity_count": len(activity_entries),
        "countries": country_counts,
        "recent_activities": activity_entries[-10:][::-1],
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EXPORT Automation System — Singing Bowls Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-color: #0c1017;
            --card-bg: #161b26;
            --card-border: #232b3b;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --accent-primary: #6366f1;
            --accent-hover: #4f46e5;
            --accent-success: #10b981;
            --accent-warning: #f59e0b;
            --accent-info: #06b6d4;
            --tag-b2b: #3b82f6;
            --tag-b2c: #8b5cf6;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 24px;
        }

        .container {
            max-width: 1380px;
            margin: 0 auto;
        }

        /* Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--card-border);
            margin-bottom: 28px;
        }

        .brand-badge {
            display: inline-block;
            background: rgba(99, 102, 241, 0.15);
            color: #818cf8;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            padding: 4px 10px;
            border-radius: 6px;
            margin-bottom: 6px;
            border: 1px solid rgba(99, 102, 241, 0.3);
        }

        h1 {
            font-size: 26px;
            font-weight: 800;
            color: var(--text-primary);
        }

        .subtitle {
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        .action-bar {
            display: flex;
            gap: 12px;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 18px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            border: none;
            transition: all 0.2s ease;
        }

        .btn-primary {
            background-color: var(--accent-primary);
            color: #fff;
        }

        .btn-primary:hover {
            background-color: var(--accent-hover);
            transform: translateY(-1px);
        }

        .btn-secondary {
            background-color: var(--card-bg);
            color: var(--text-primary);
            border: 1px solid var(--card-border);
        }

        .btn-secondary:hover {
            background-color: #1f2737;
        }

        /* Metrics Row */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 18px;
            margin-bottom: 28px;
        }

        .metric-card {
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }

        .metric-card:hover {
            transform: translateY(-2px);
            border-color: #3b4559;
        }

        .metric-label {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .metric-value {
            font-size: 32px;
            font-weight: 800;
            color: var(--text-primary);
        }

        .metric-desc {
            font-size: 12px;
            color: var(--text-secondary);
        }

        /* Charts & Visuals */
        .charts-grid {
            display: grid;
            grid-template-columns: 1fr 1.5fr;
            gap: 20px;
            margin-bottom: 28px;
        }

        .chart-card {
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
        }

        .chart-title {
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 16px;
            color: var(--text-primary);
        }

        /* Tabs Navigation */
        .tabs {
            display: flex;
            gap: 8px;
            border-bottom: 1px solid var(--card-border);
            margin-bottom: 20px;
        }

        .tab-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 14px;
            font-weight: 600;
            padding: 12px 18px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s ease;
        }

        .tab-btn:hover {
            color: var(--text-primary);
        }

        .tab-btn.active {
            color: var(--accent-primary);
            border-bottom-color: var(--accent-primary);
        }

        /* Tables */
        .table-card {
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            overflow: hidden;
        }

        .table-responsive {
            width: 100%;
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }

        th {
            background-color: #11151f;
            color: var(--text-secondary);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 14px 16px;
            border-bottom: 1px solid var(--card-border);
        }

        td {
            padding: 14px 16px;
            border-bottom: 1px solid #1c2331;
            color: #d1d7e0;
        }

        tr:hover td {
            background-color: rgba(255, 255, 255, 0.02);
        }

        /* Badges */
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }

        .badge-b2b {
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }

        .badge-b2c {
            background: rgba(139, 92, 246, 0.15);
            color: #a78bfa;
            border: 1px solid rgba(139, 92, 246, 0.3);
        }

        .badge-success {
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .badge-info {
            background: rgba(6, 182, 212, 0.15);
            color: #22d3ee;
            border: 1px solid rgba(6, 182, 212, 0.3);
        }

        .badge-warning {
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        /* Toast / Notification */
        #notification {
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 14px 20px;
            background: #1f2937;
            border: 1px solid var(--accent-primary);
            border-radius: 8px;
            color: #fff;
            font-size: 14px;
            font-weight: 600;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
            z-index: 1000;
        }

        #notification.show {
            transform: translateY(0);
            opacity: 1;
        }

        @media (max-width: 900px) {
            .charts-grid {
                grid-template-columns: 1fr;
            }
            header {
                flex-direction: column;
                align-items: flex-start;
                gap: 16px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <span class="brand-badge">Singing Bowls Global Export</span>
                <h1>EXPORT Automation System</h1>
                <p class="subtitle">Real-time Lead Discovery, AI Classification & Outreach Dashboard</p>
            </div>
            <div class="action-bar">
                <button class="btn btn-secondary" onclick="loadDashboard()">🔄 Refresh Data</button>
                <button class="btn btn-primary" onclick="triggerPipeline()">⚡ Run Discovery Pipeline</button>
            </div>
        </header>

        <!-- Metric Cards -->
        <div class="metrics-grid">
            <div class="metric-card">
                <span class="metric-label">Master Catalog</span>
                <span class="metric-value" id="val-total">0</span>
                <span class="metric-desc">Verified unique buyers (buyers.csv)</span>
            </div>
            <div class="metric-card">
                <span class="metric-label">B2B Wholesale Targets</span>
                <span class="metric-value" style="color: #60a5fa;" id="val-b2b">0</span>
                <span class="metric-desc">Studios, Spas & Wholesalers</span>
            </div>
            <div class="metric-card">
                <span class="metric-label">B2C Retail Contacts</span>
                <span class="metric-value" style="color: #a78bfa;" id="val-b2c">0</span>
                <span class="metric-desc">Individual practitioners & collectors</span>
            </div>
            <div class="metric-card">
                <span class="metric-label">Sent Outreach</span>
                <span class="metric-value" style="color: #34d399;" id="val-sent">0</span>
                <span class="metric-desc">Phase 3 logged attempts</span>
            </div>
            <div class="metric-card">
                <span class="metric-label">Audit Logs</span>
                <span class="metric-value" style="color: #22d3ee;" id="val-logs">0</span>
                <span class="metric-desc">Traceable pipeline events</span>
            </div>
        </div>

        <!-- Charts Section -->
        <div class="charts-grid">
            <div class="chart-card">
                <h3 class="chart-title">B2B vs B2C Segregation</h3>
                <div style="position: relative; height: 260px; display: flex; justify-content: center;">
                    <canvas id="b2bPieChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h3 class="chart-title">Global Buyer Distribution by Country</h3>
                <div style="position: relative; height: 260px;">
                    <canvas id="countryBarChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Tabs Navigation -->
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('business-tab', this)">B2B Wholesale Leads (Priority)</button>
            <button class="tab-btn" onclick="switchTab('individual-tab', this)">B2C Individual Leads</button>
            <button class="tab-btn" onclick="switchTab('master-tab', this)">Master Catalog (buyers.csv)</button>
            <button class="tab-btn" onclick="switchTab('activity-tab', this)">Live Audit Trail</button>
        </div>

        <!-- Tab 1: B2B Wholesale Leads -->
        <div id="business-tab" class="tab-content table-card">
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Buyer Name</th>
                            <th>Company</th>
                            <th>Email</th>
                            <th>Website</th>
                            <th>Country</th>
                            <th>AI Rationale</th>
                        </tr>
                    </thead>
                    <tbody id="business-tbody">
                        <tr><td colspan="6" style="text-align: center; color: var(--text-secondary);">Loading B2B leads...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Tab 2: B2C Individual Leads -->
        <div id="individual-tab" class="tab-content table-card" style="display: none;">
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Buyer Name</th>
                            <th>Email</th>
                            <th>Country</th>
                            <th>Source Platform</th>
                            <th>AI Rationale</th>
                        </tr>
                    </thead>
                    <tbody id="individual-tbody">
                        <tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">Loading B2C leads...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Tab 3: Master Catalog -->
        <div id="master-tab" class="tab-content table-card" style="display: none;">
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Buyer Name</th>
                            <th>Company</th>
                            <th>Email</th>
                            <th>Website</th>
                            <th>Country</th>
                            <th>Source Platform</th>
                        </tr>
                    </thead>
                    <tbody id="master-tbody">
                        <tr><td colspan="6" style="text-align: center; color: var(--text-secondary);">Loading master catalog...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Tab 4: Audit Trail -->
        <div id="activity-tab" class="tab-content table-card" style="display: none;">
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Event Category</th>
                            <th>Email</th>
                            <th>Status</th>
                            <th>Message</th>
                        </tr>
                    </thead>
                    <tbody id="activity-tbody">
                        <tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">Loading audit logs...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <div id="notification">Notification message</div>

    <script>
        let pieChart = null;
        let barChart = null;

        function showNotification(msg) {
            const notif = document.getElementById("notification");
            notif.innerText = msg;
            notif.classList.add("show");
            setTimeout(() => notif.classList.remove("show"), 3500);
        }

        function switchTab(tabId, btn) {
            document.querySelectorAll(".tab-content").forEach(el => el.style.display = "none");
            document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));
            document.getElementById(tabId).style.display = "block";
            btn.classList.add("active");
        }

        async function loadDashboard() {
            try {
                const res = await fetch("/api/data");
                const data = await res.json();

                // Populate metrics
                document.getElementById("val-total").innerText = data.stats.total_buyers;
                document.getElementById("val-b2b").innerText = data.stats.b2b_buyers;
                document.getElementById("val-b2c").innerText = data.stats.b2c_buyers;
                document.getElementById("val-sent").innerText = data.stats.sent_count;
                document.getElementById("val-logs").innerText = data.stats.activity_count;

                // Render Charts
                renderPieChart(data.stats.b2b_buyers, data.stats.b2c_buyers);
                renderBarChart(data.stats.countries);

                // Populate Tables
                renderB2BTable(data.b2b);
                renderB2CTable(data.b2c);
                renderMasterTable(data.master);
                renderActivityTable(data.activities);

            } catch (err) {
                console.error("Failed to load dashboard data:", err);
            }
        }

        function renderPieChart(b2b, b2c) {
            const ctx = document.getElementById('b2bPieChart').getContext('2d');
            if (pieChart) pieChart.destroy();
            pieChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['B2B Wholesale', 'B2C Individual'],
                    datasets: [{
                        data: [b2b, b2c],
                        backgroundColor: ['#3b82f6', '#8b5cf6'],
                        borderColor: '#161b26',
                        borderWidth: 3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { color: '#8b949e', font: { family: 'Plus Jakarta Sans', size: 12 } }
                        }
                    }
                }
            });
        }

        function renderBarChart(countries) {
            const ctx = document.getElementById('countryBarChart').getContext('2d');
            if (barChart) barChart.destroy();
            const labels = Object.keys(countries);
            const values = Object.values(countries);

            barChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Buyers',
                        data: values,
                        backgroundColor: '#6366f1',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { ticks: { color: '#8b949e' }, grid: { display: false } },
                        y: { ticks: { color: '#8b949e', precision: 0 }, grid: { color: '#232b3b' } }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }

        function renderB2BTable(records) {
            const tbody = document.getElementById("business-tbody");
            if (!records || records.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary);">No B2B wholesale buyers found yet. Run discovery to populate.</td></tr>`;
                return;
            }
            tbody.innerHTML = records.map(r => `
                <tr>
                    <td style="font-weight: 600; color: #fff;">${r.buyer_name || '-'}</td>
                    <td>${r.company_name || '-'}</td>
                    <td><a href="mailto:${r.email}" style="color: #60a5fa; text-decoration: none;">${r.email}</a></td>
                    <td>${r.website ? `<a href="${r.website}" target="_blank" style="color: #818cf8; text-decoration: none;">Link ↗</a>` : '-'}</td>
                    <td><span class="badge badge-info">${r.country || 'Global'}</span></td>
                    <td style="font-size: 12px; color: var(--text-secondary);">${r.reasoning || '-'}</td>
                </tr>
            `).join("");
        }

        function renderB2CTable(records) {
            const tbody = document.getElementById("individual-tbody");
            if (!records || records.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No B2C leads recorded.</td></tr>`;
                return;
            }
            tbody.innerHTML = records.map(r => `
                <tr>
                    <td style="font-weight: 600; color: #fff;">${r.buyer_name || '-'}</td>
                    <td><a href="mailto:${r.email}" style="color: #a78bfa; text-decoration: none;">${r.email}</a></td>
                    <td><span class="badge badge-info">${r.country || 'Global'}</span></td>
                    <td>${r.source_platform || '-'}</td>
                    <td style="font-size: 12px; color: var(--text-secondary);">${r.reasoning || '-'}</td>
                </tr>
            `).join("");
        }

        function renderMasterTable(records) {
            const tbody = document.getElementById("master-tbody");
            if (!records || records.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary);">Catalog is empty.</td></tr>`;
                return;
            }
            tbody.innerHTML = records.map(r => `
                <tr>
                    <td style="font-weight: 600; color: #fff;">${r.buyer_name || '-'}</td>
                    <td>${r.company_name || '-'}</td>
                    <td><a href="mailto:${r.email}" style="color: #60a5fa; text-decoration: none;">${r.email}</a></td>
                    <td>${r.website ? `<a href="${r.website}" target="_blank" style="color: #818cf8; text-decoration: none;">Link ↗</a>` : '-'}</td>
                    <td><span class="badge badge-info">${r.country || 'Global'}</span></td>
                    <td>${r.source_platform || '-'}</td>
                </tr>
            `).join("");
        }

        function renderActivityTable(records) {
            const tbody = document.getElementById("activity-tbody");
            if (!records || records.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">No audit logs found.</td></tr>`;
                return;
            }
            tbody.innerHTML = records.map(r => {
                let badgeClass = "badge-info";
                if (r.status === "SUCCESS" || r.status === "BUSINESS") badgeClass = "badge-success";
                if (r.status === "REJECTED" || r.status === "FAILED") badgeClass = "badge-warning";
                if (r.status === "INDIVIDUAL") badgeClass = "badge-b2c";
                return `
                    <tr>
                        <td style="font-family: monospace; font-size: 12px; color: var(--text-secondary);">${r.timestamp}</td>
                        <td style="font-weight: 600;">${r.event}</td>
                        <td>${r.email || '-'}</td>
                        <td><span class="badge ${badgeClass}">${r.status}</span></td>
                        <td>${r.message}</td>
                    </tr>
                `;
            }).join("");
        }

        async function triggerPipeline() {
            showNotification("⚡ Running Lead Discovery & AI Classification...");
            try {
                const res = await fetch("/api/run-pipeline", { method: "POST" });
                const json = await res.json();
                showNotification("✅ " + json.message);
                await loadDashboard();
            } catch (err) {
                showNotification("❌ Failed to trigger pipeline");
            }
        }

        window.onload = loadDashboard;
    </script>
</body>
</html>
"""


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler providing REST API and serving the dashboard UI."""

    def log_message(self, format: str, *args: Any) -> None:
        """Silence standard console logging for clean CLI output."""
        return

    def do_GET(self) -> None:
        """Handle GET requests for HTML page and JSON API."""
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path in ("/", "/dashboard"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))

        elif parsed.path == "/api/data":
            stats = get_dashboard_stats()
            master = read_all_buyers()
            b2b = read_classified_buyers("BUSINESS")
            b2c = read_classified_buyers("INDIVIDUAL")

            # Read full activity log entries (most recent first)
            activities = []
            if config.ACTIVITY_LOG_CSV.exists():
                with open(config.ACTIVITY_LOG_CSV, mode="r", newline="", encoding="utf-8") as f:
                    activities = list(csv.DictReader(f))[-50:][::-1]

            payload = {
                "stats": stats,
                "master": master,
                "b2b": b2b,
                "b2c": b2c,
                "activities": activities,
            }

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))

        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def do_POST(self) -> None:
        """Handle POST requests to trigger pipeline execution."""
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/run-pipeline":
            # Run the discovery & classification pipeline
            main.run_pipeline()

            response = {"status": "success", "message": "Discovery pipeline completed successfully!"}
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")


def start_server(port: int = 5000) -> None:
    """Launch the dashboard HTTP server."""
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, DashboardRequestHandler)
    print("=" * 65)
    print(f"EXPORT Automation Dashboard is live at: http://localhost:{port}")
    print("Open this URL in your web browser to explore your Singing Bowls leads.")
    print("Press Ctrl+C to stop the dashboard server.")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server.")
        httpd.server_close()


if __name__ == "__main__":
    start_server(5000)
