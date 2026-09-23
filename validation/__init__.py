"""Email validation and outreach duplicate screening package."""

from .email_validator import (
    check_outreach_eligibility,
    is_duplicate_buyer,
    is_duplicate_outreach,
    is_valid_email,
)

__all__ = [
    "is_valid_email",
    "is_duplicate_buyer",
    "is_duplicate_outreach",
    "check_outreach_eligibility",
]
