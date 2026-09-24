"""Outreach dispatcher and SMTP manager for EXPORT Automation System (Phase 4).

Handles:
- MIME multipart email assembly with plain text, rich HTML, and PDF catalog attachments.
- Secure Gmail SMTP delivery (SSL on port 465 / TLS on port 587).
- Safe offline simulation / dry-run execution in TEST_MODE (zero network calls, zero spam risk).
- Pre-flight screening: duplicate prevention (sent_log.csv), RFC email syntax validation, and daily quota limits.
- Real-time audit logging and dispatch metrics aggregation.
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from email import utils
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from pathlib import Path
import smtplib
import time
from typing import Any, Dict, List, Optional, Tuple

import config
from logging_module.activity_logger import (
    is_sent_successfully,
    log_activity,
    log_sent_entry,
)
from outreach.rate_limiter import can_send_today
from outreach.template_manager import EmailDraft, render_email_draft
from validation.email_validator import is_valid_email


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OutreachResult:
    """Represents the outcome of a single email outreach attempt."""

    email: str
    status: str  # 'SUCCESS', 'SIMULATED_SUCCESS', 'SKIPPED_PREVIOUSLY_SENT', 'SKIPPED_DAILY_LIMIT', 'REJECTED_INVALID_EMAIL', 'FAILED'
    message: str
    subject: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return asdict(self)


@dataclass
class OutreachStatistics:
    """Aggregates execution metrics for Phase 4 outreach campaigns."""

    total_targeted: int = 0
    sent_count: int = 0
    simulated_count: int = 0
    skipped_duplicate: int = 0
    skipped_daily_limit: int = 0
    rejected_count: int = 0
    failed_count: int = 0

    def record(self, result: OutreachResult) -> None:
        """Record the result of an outreach attempt."""
        self.total_targeted += 1
        if result.status == "SUCCESS":
            self.sent_count += 1
        elif result.status == "SIMULATED_SUCCESS":
            self.simulated_count += 1
        elif result.status == "SKIPPED_PREVIOUSLY_SENT":
            self.skipped_duplicate += 1
        elif result.status == "SKIPPED_DAILY_LIMIT":
            self.skipped_daily_limit += 1
        elif result.status == "REJECTED_INVALID_EMAIL":
            self.rejected_count += 1
        elif result.status == "FAILED":
            self.failed_count += 1

    def summary(self) -> Dict[str, int]:
        """Return summary metrics as a dictionary."""
        return {
            "total_targeted": self.total_targeted,
            "sent_count": self.sent_count,
            "simulated_count": self.simulated_count,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_daily_limit": self.skipped_daily_limit,
            "rejected_count": self.rejected_count,
            "failed_count": self.failed_count,
        }


# ==============================================================================
# MIME MESSAGE BUILDER
# ==============================================================================
def build_mime_message(
    draft: EmailDraft,
    sender_email: Optional[str] = None,
    sender_name: Optional[str] = None,
) -> MIMEMultipart:
    """Construct a MIME multipart email containing plain text, HTML, and attachment.

    Args:
        draft: EmailDraft containing subject, bodies, recipient, and optional attachment.
        sender_email: Optional sender email override.
        sender_name: Optional sender display name override.

    Returns:
        MIMEMultipart message object ready for SMTP transmission.
    """
    from_email = sender_email or config.GMAIL_EMAIL or "export@himalayanartisanbowls.com"
    from_name = sender_name or config.SENDER_NAME

    msg = MIMEMultipart("mixed")
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    msg["To"] = f"{draft.to_name} <{draft.to_email}>" if draft.to_name else draft.to_email
    msg["Subject"] = draft.subject
    msg["Date"] = utils.formatdate(localtime=True)
    msg["Message-ID"] = utils.make_msgid(domain="himalayanartisanbowls.com")

    # Alternative part for Text and HTML bodies
    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(draft.body_text, "plain", "utf-8"))
    alt_part.attach(MIMEText(draft.body_html, "html", "utf-8"))
    msg.attach(alt_part)

    # Attach PDF presentation if specified and present
    if draft.attachment_path:
        att_path = Path(draft.attachment_path)
        if att_path.exists() and att_path.is_file():
            try:
                with open(att_path, "rb") as f:
                    pdf_data = f.read()
                pdf_part = MIMEApplication(pdf_data, _subtype="pdf")
                pdf_filename = att_path.name if att_path.name.endswith(".pdf") else "Company_Presentation.pdf"
                pdf_part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=pdf_filename,
                )
                msg.attach(pdf_part)
            except Exception:
                pass  # Fall back cleanly if attachment cannot be read

    return msg


# ==============================================================================
# DISPATCH ENGINES (SIMULATED & LIVE)
# ==============================================================================
def send_single_email(
    buyer: Dict[str, str],
    dry_run: Optional[bool] = None,
    test_mode: Optional[bool] = None,
    sent_log_path: Optional[Path] = None,
    activity_log_path: Optional[Path] = None,
) -> OutreachResult:
    """Evaluate and dispatch an outreach email to a single buyer.

    Performs pre-flight eligibility screening:
    1. Email syntax validation.
    2. Duplicate check against sent_log.csv.
    3. Daily rate limit quota check.

    If in TEST_MODE, dry_run=True, or credentials missing: simulates delivery safely.

    Args:
        buyer: Normalized buyer lead dictionary.
        dry_run: Explicit dry-run toggle; defaults to config.DRY_RUN.
        test_mode: Explicit test mode toggle; defaults to config.TEST_MODE.
        sent_log_path: Optional custom sent_log.csv path.
        activity_log_path: Optional custom activity_log.csv path.

    Returns:
        OutreachResult object detailing outcome.
    """
    email = (buyer.get("email") or "").strip().lower()
    now_ts = datetime.now().isoformat(timespec="seconds")

    # 1. Syntax validation
    if not is_valid_email(email):
        log_activity(
            event="OUTREACH_VALIDATION",
            email=email,
            status="INVALID_EMAIL",
            message="Skipped outreach: email address failed syntax validation.",
            csv_path=activity_log_path,
        )
        return OutreachResult(
            email=email,
            status="REJECTED_INVALID_EMAIL",
            message="Email address failed syntax validation.",
            timestamp=now_ts,
        )

    # 2. Duplicate screening
    if is_sent_successfully(email, sent_log_path):
        log_activity(
            event="OUTREACH_DUPLICATE",
            email=email,
            status="SKIPPED",
            message=f"Duplicate outreach suppressed: '{email}' already contacted successfully.",
            csv_path=activity_log_path,
        )
        return OutreachResult(
            email=email,
            status="SKIPPED_PREVIOUSLY_SENT",
            message=f"Email '{email}' has already been contacted.",
            timestamp=now_ts,
        )

    # 3. Daily rate limit check
    can_send, current_sent, max_limit = can_send_today(sent_log_path=sent_log_path)
    if not can_send:
        log_activity(
            event="OUTREACH_RATE_LIMIT",
            email=email,
            status="LIMIT_REACHED",
            message=f"Skipped outreach: Daily send limit of {max_limit} reached ({current_sent} sent today).",
            csv_path=activity_log_path,
        )
        return OutreachResult(
            email=email,
            status="SKIPPED_DAILY_LIMIT",
            message=f"Daily send quota reached ({current_sent}/{max_limit}).",
            timestamp=now_ts,
        )

    # 4. Render personalized draft
    draft = render_email_draft(buyer)

    # 5. Determine whether to run in Simulation / Dry-Run Mode
    is_test = config.TEST_MODE if test_mode is None else test_mode
    is_dry = config.DRY_RUN if dry_run is None else dry_run
    has_credentials = bool(config.GMAIL_EMAIL and config.GMAIL_APP_PASSWORD)

    run_simulation = is_test or is_dry or not has_credentials

    # Build MIME message to verify integrity in all modes
    mime_msg = build_mime_message(draft)

    if run_simulation:
        # SIMULATION / DRY-RUN MODE: Zero network calls, zero spam
        log_sent_entry(email, "SIMULATED_SUCCESS", sent_log_path)
        log_activity(
            event="OUTREACH_SIMULATED",
            email=email,
            status="SIMULATED_SUCCESS",
            message=f"Simulated email delivery. Subject: '{draft.subject}' (TEST_MODE dry-run).",
            csv_path=activity_log_path,
        )
        return OutreachResult(
            email=email,
            status="SIMULATED_SUCCESS",
            message="Simulated delivery successful (Dry Run / TEST_MODE).",
            subject=draft.subject,
            timestamp=now_ts,
        )

    # LIVE GMAIL SMTP TRANSMISSION
    try:
        if config.USE_SSL:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
            server.starttls()

        server.login(config.GMAIL_EMAIL, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_EMAIL, [email], mime_msg.as_string())
        server.quit()

        log_sent_entry(email, "SUCCESS", sent_log_path)
        log_activity(
            event="OUTREACH_SENT",
            email=email,
            status="SUCCESS",
            message=f"Dispatched email to '{email}'. Subject: '{draft.subject}'.",
            csv_path=activity_log_path,
        )
        return OutreachResult(
            email=email,
            status="SUCCESS",
            message="Email successfully dispatched via Gmail SMTP.",
            subject=draft.subject,
            timestamp=now_ts,
        )
    except Exception as e:
        log_sent_entry(email, "FAILED", sent_log_path)
        log_activity(
            event="OUTREACH_FAILED",
            email=email,
            status="FAILED",
            message=f"SMTP transmission error: {str(e)}",
            csv_path=activity_log_path,
        )
        return OutreachResult(
            email=email,
            status="FAILED",
            message=f"SMTP transmission failure: {str(e)}",
            subject=draft.subject,
            timestamp=now_ts,
        )


def send_batch_outreach(
    buyers: List[Dict[str, str]],
    target_tiers: Optional[List[str]] = None,
    dry_run: Optional[bool] = None,
    test_mode: Optional[bool] = None,
    delay_seconds: float = 0.0,
    sent_log_path: Optional[Path] = None,
    activity_log_path: Optional[Path] = None,
) -> Tuple[List[OutreachResult], OutreachStatistics]:
    """Execute a batch email outreach campaign across qualified buyers.

    Args:
        buyers: List of buyer lead dictionaries.
        target_tiers: List of priority tiers to include (defaults to Tier 1 and Tier 2).
        dry_run: Toggle for dry-run simulation mode.
        test_mode: Toggle for test mode.
        delay_seconds: Politeness delay between successive dispatches.
        sent_log_path: Optional custom sent_log.csv path.
        activity_log_path: Optional custom activity_log.csv path.

    Returns:
        Tuple of (list of OutreachResults, OutreachStatistics).
    """
    eligible_tiers = target_tiers if target_tiers is not None else [config.TIER_1, config.TIER_2]
    stats = OutreachStatistics()
    results: List[OutreachResult] = []

    for idx, buyer in enumerate(buyers):
        buyer_tier = (buyer.get("tier") or "").strip()

        # Filter: only outreach to targeted priority tiers
        if eligible_tiers and not any(t in buyer_tier for t in eligible_tiers):
            continue

        result = send_single_email(
            buyer=buyer,
            dry_run=dry_run,
            test_mode=test_mode,
            sent_log_path=sent_log_path,
            activity_log_path=activity_log_path,
        )
        results.append(result)
        stats.record(result)

        # Halt if daily limit is reached
        if result.status == "SKIPPED_DAILY_LIMIT":
            break

        # Politeness delay between live sends
        if delay_seconds > 0 and idx < len(buyers) - 1 and result.status in ("SUCCESS", "SIMULATED_SUCCESS"):
            time.sleep(delay_seconds)

    return results, stats
