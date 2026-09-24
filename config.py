"""Configuration module for EXPORT Automation System (Phase 1 & Phase 2).

Loads environment variables and sets up project paths and default parameters.
"""

import os
from pathlib import Path

# Attempt to load .env variables via python-dotenv if installed
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

# ==============================================================================
# PROJECT PATHS
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BUYERS_CSV = DATA_DIR / "buyers.csv"
BUSINESS_BUYERS_CSV = DATA_DIR / "business_buyers.csv"
INDIVIDUAL_BUYERS_CSV = DATA_DIR / "individual_buyers.csv"
SENT_LOG_CSV = DATA_DIR / "sent_log.csv"
ACTIVITY_LOG_CSV = DATA_DIR / "activity_log.csv"
ASSETS_DIR = BASE_DIR / "assets"

# ==============================================================================
# APPLICATION & DISCOVERY SETTINGS
# ==============================================================================
TEST_MODE = os.getenv("TEST_MODE", "True").lower() in ("true", "1", "yes")
SEARCH_KEYWORD = os.getenv("SEARCH_KEYWORD", "Singing Bowls wholesale imports studio")

# Data Quality Status Constants
STATUS_VALID = "VALID"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_INVALID_EMAIL = "INVALID_EMAIL"
STATUS_DUPLICATE = "DUPLICATE"
STATUS_REJECTED = "REJECTED"

try:
    DAILY_SEND_LIMIT = int(os.getenv("DAILY_SEND_LIMIT", "100"))
except ValueError:
    DAILY_SEND_LIMIT = 100

presentation_env = os.getenv("PRESENTATION_PATH", "assets/company_presentation.pdf")
PRESENTATION_PATH = BASE_DIR / presentation_env

# ==============================================================================
# GEMINI AI CLASSIFICATION SETTINGS
# ==============================================================================
# Optional: If GEMINI_API_KEY is provided, AI classification uses Google Gemini.
# If empty or not set, the system falls back seamlessly to rule-based heuristics.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ==============================================================================
# GMAIL PLACEHOLDERS (FOR FUTURE PHASE 3 OUTREACH)
# ==============================================================================
# IMPORTANT:
# The Gmail variables below are strictly placeholders for Phase 3.
# Phase 1 & 2 NEVER send real emails.
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
