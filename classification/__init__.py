"""Buyer classification package."""

from .classifier import (
    BUSINESS_KEYWORDS,
    FREEMAIL_DOMAINS,
    classify_buyer,
    heuristic_classify,
)

__all__ = [
    "classify_buyer",
    "heuristic_classify",
    "BUSINESS_KEYWORDS",
    "FREEMAIL_DOMAINS",
]
