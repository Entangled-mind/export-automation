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
from html import escape as html_escape
from email import utils
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from pathlib import Path
import smtplib
import socket
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
    subject_override: Optional[str] = None,
    body_text_override: Optional[str] = None,
    sender_name: Optional[str] = None,
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
    if subject_override is not None:
        draft.subject = subject_override
    if body_text_override is not None:
        draft.body_text = body_text_override
        paragraphs = "".join(
            f"<p>{html_escape(part)}</p>"
            for part in body_text_override.split("\n\n")
            if part.strip()
        )
        draft.body_html = f"<html><body>{paragraphs}</body></html>"

    # 5. Determine whether to run in Simulation / Dry-Run Mode
    is_test = config.TEST_MODE if test_mode is None else test_mode
    is_dry = config.DRY_RUN if dry_run is None else dry_run
    has_credentials = bool(config.GMAIL_EMAIL and config.GMAIL_APP_PASSWORD)

    run_simulation = is_test or is_dry or not has_credentials

    # Build MIME message to verify integrity in all modes
    mime_msg = build_mime_message(draft, sender_name=sender_name)

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
        clean_pwd = config.GMAIL_APP_PASSWORD.replace(" ", "").strip()
        ports_to_try = (
            [(config.SMTP_PORT, config.USE_SSL), (465, True), (587, False)]
            if config.USE_SSL or config.SMTP_PORT == 465
            else [(config.SMTP_PORT, config.USE_SSL), (587, False), (465, True)]
        )

        # Deduplicate ports list while preserving order
        unique_ports = []
        for p, s in ports_to_try:
            if (p, s) not in unique_ports:
                unique_ports.append((p, s))

        server = None
        last_exception = None
        for port, use_ssl in unique_ports:
            try:
                if use_ssl:
                    server = smtplib.SMTP_SSL(config.SMTP_HOST, port, timeout=15)
                else:
                    server = smtplib.SMTP(config.SMTP_HOST, port, timeout=15)
                    server.starttls()
                server.login(config.GMAIL_EMAIL.strip(), clean_pwd)
                break
            except smtplib.SMTPAuthenticationError as auth_err:
                last_exception = auth_err
                break  # Don't retry another port if credentials are bad
            except Exception as conn_err:
                last_exception = conn_err
                err_str = str(conn_err).lower()
                # If it's an authentication error, stop immediately without trying other ports
                if "authentication failed" in err_str or "535" in err_str or "badcredentials" in err_str:
                    break
                # Only retry other ports for network/socket connection errors
                if not isinstance(conn_err, (socket.error, OSError, TimeoutError, ConnectionError)):
                    break
                server = None
                continue

        if not server:
            raise last_exception or RuntimeError("Could not connect to Gmail SMTP server.")

        server.sendmail(config.GMAIL_EMAIL.strip(), [email], mime_msg.as_string())
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
        error_text = str(e)
        if getattr(e, "winerror", None) == 10013 or "WinError 10013" in error_text:
            failure_message = (
                "Windows blocked this app's SMTP connection (WinError 10013). "
                "The email was not sent; open the prepared email in your mail app to send it."
            )
        elif isinstance(e, smtplib.SMTPAuthenticationError):
            failure_message = (
                "Gmail authentication failed (BadCredentials). Check your 16-character Google App Password in settings."
            )
        else:
            failure_message = f"SMTP transmission failure: {error_text}"
        log_sent_entry(email, "FAILED", sent_log_path)
        log_activity(
            event="OUTREACH_FAILED",
            email=email,
            status="FAILED",
            message=failure_message,
            csv_path=activity_log_path,
        )
        return OutreachResult(
            email=email,
            status="FAILED",
            message=failure_message,
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


def test_smtp_credentials(
    email: Optional[str] = None,
    password: Optional[str] = None,
    host: Optional[str] = None,
) -> Tuple[bool, str]:
    """Test connection and authentication with Gmail SMTP server.

    Returns:
        (is_authenticated: bool, status_message: str)
    """
    target_email = (email if email is not None else (config.GMAIL_EMAIL or "")).strip()
    target_pwd = (password if password is not None else (config.GMAIL_APP_PASSWORD or "")).strip()
    target_host = host or config.SMTP_HOST

    if not target_email:
        return False, "Gmail address is not provided."
    if not target_pwd or target_pwd == "your_16_character_app_password":
        return False, "Google App Password is not set or is still the default placeholder."

    clean_pwd = target_pwd.replace(" ", "").strip()
    ports_to_try = [(465, True), (587, False)]
    last_err = ""

    for port, use_ssl in ports_to_try:
        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(target_host, port, timeout=10)
            else:
                server = smtplib.SMTP(target_host, port, timeout=10)
                server.starttls()
            server.login(target_email, clean_pwd)
            server.quit()
            return True, f"Successfully connected to Gmail as {target_email}!"
        except smtplib.SMTPAuthenticationError:
            return (
                False,
                "Authentication failed: Google rejected this App Password. "
                "Ensure you generated a 16-character App Password at myaccount.google.com/apppasswords."
            )
        except Exception as e:
            last_err = str(e)
            continue

    return False, f"Could not connect to Gmail SMTP: {last_err or 'Connection timed out'}"


def save_email_credentials(
    email: str,
    password: str,
    sender_name: Optional[str] = None,
    sender_company: Optional[str] = None,
    env_path: Optional[Path] = None,
) -> bool:
    """Persist verified Gmail SMTP credentials to .env and runtime config."""
    clean_email = email.strip()
    clean_pwd = password.replace(" ", "").strip()
    target_env = env_path or (config.BASE_DIR / ".env")

    # Update in-memory config immediately
    config.GMAIL_EMAIL = clean_email
    config.GMAIL_APP_PASSWORD = clean_pwd
    config.SMTP_PORT = 465
    config.USE_SSL = True
    config.DRY_RUN = False
    config.TEST_MODE = False
    if sender_name:
        config.SENDER_NAME = sender_name.strip()
    if sender_company:
        config.SENDER_COMPANY = sender_company.strip()

    # Update .env file on disk
    try:
        env_lines = []
        if target_env.exists():
            with open(target_env, "r", encoding="utf-8") as f:
                env_lines = f.readlines()

        keys_updated = {
            "GMAIL_EMAIL": clean_email,
            "GMAIL_APP_PASSWORD": clean_pwd,
            "SMTP_PORT": "465",
            "USE_SSL": "True",
            "DRY_RUN": "False",
            "TEST_MODE": "False",
        }
        if sender_name:
            keys_updated["SENDER_NAME"] = sender_name.strip()
        if sender_company:
            keys_updated["SENDER_COMPANY"] = sender_company.strip()

        written_keys = set()
        new_lines = []
        for line in env_lines:
            key_match = False
            for k, val in keys_updated.items():
                if line.startswith(f"{k}=") or line.startswith(f"{k} ="):
                    new_lines.append(f"{k}={val}\n")
                    written_keys.add(k)
                    key_match = True
                    break
            if not key_match:
                new_lines.append(line)

        for k, val in keys_updated.items():
            if k not in written_keys:
                new_lines.append(f"{k}={val}\n")

        with open(target_env, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return True
    except Exception:
        return False

