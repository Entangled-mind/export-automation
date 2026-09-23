"""Data extraction, normalization, and segregated storage package."""

from .data_extractor import (
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

__all__ = [
    "BUYER_FIELDS",
    "CLASSIFIED_FIELDS",
    "normalize_email",
    "normalize_buyer",
    "init_buyers_csv",
    "init_classified_csv",
    "read_all_buyers",
    "read_classified_buyers",
    "buyer_email_exists",
    "add_buyer",
    "add_classified_buyer",
]
