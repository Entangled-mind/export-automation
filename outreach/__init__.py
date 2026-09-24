"""Outreach and email automation package for EXPORT Automation System (Phase 4)."""

from .email_sender import (
    OutreachResult,
    OutreachStatistics,
    build_mime_message,
    send_batch_outreach,
    send_single_email,
)
from .rate_limiter import can_send_today, get_today_sent_count
from .template_manager import (
    DEFAULT_TIER1_ANGLE,
    DEFAULT_TIER2_ANGLE,
    DEFAULT_TIER3_ANGLE,
    EmailDraft,
    get_personalized_placeholders,
    render_email_draft,
)

__all__ = [
    "send_single_email",
    "send_batch_outreach",
    "build_mime_message",
    "OutreachResult",
    "OutreachStatistics",
    "EmailDraft",
    "render_email_draft",
    "get_personalized_placeholders",
    "can_send_today",
    "get_today_sent_count",
    "DEFAULT_TIER1_ANGLE",
    "DEFAULT_TIER2_ANGLE",
    "DEFAULT_TIER3_ANGLE",
]
