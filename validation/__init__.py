"""Validation and Data Quality package for EXPORT Automation System."""

from .data_quality import (
    STATUS_DUPLICATE,
    STATUS_INCOMPLETE,
    STATUS_INVALID_EMAIL,
    STATUS_REJECTED,
    STATUS_VALID,
    DiscoveryStatistics,
    assess_lead_quality,
)
from .email_validator import (
    check_outreach_eligibility,
    is_duplicate_buyer,
    is_duplicate_outreach,
    is_placeholder_email,
    is_valid_email,
)

__all__ = [
    "is_valid_email",
    "is_placeholder_email",
    "is_duplicate_buyer",
    "is_duplicate_outreach",
    "check_outreach_eligibility",
    "assess_lead_quality",
    "DiscoveryStatistics",
    "STATUS_VALID",
    "STATUS_INCOMPLETE",
    "STATUS_INVALID_EMAIL",
    "STATUS_DUPLICATE",
    "STATUS_REJECTED",
]
