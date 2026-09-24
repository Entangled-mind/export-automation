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
DB_PATH = DATA_DIR / "export_automation.db"
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
# GEMINI AI CLASSIFICATION SETTINGS (PHASE 3)
# ==============================================================================
# Optional: If GEMINI_API_KEY is provided, AI classification uses Google Gemini.
# If empty or not set, the system falls back seamlessly to rule-based heuristics.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Lead Classification & Priority Tiers
TIER_1 = "Tier 1 - High Priority"
TIER_2 = "Tier 2 - Medium Priority"
TIER_3 = "Tier 3 - Low Priority"
TIER_IRRELEVANT = "Irrelevant / Unqualified"

CATEGORY_BUSINESS = "BUSINESS"
CATEGORY_INDIVIDUAL = "INDIVIDUAL"
CATEGORY_IRRELEVANT = "IRRELEVANT"

# ==============================================================================
# GMAIL OUTREACH SETTINGS (PHASE 4)
# ==============================================================================
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
try:
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
except ValueError:
    SMTP_PORT = 465
USE_SSL = os.getenv("USE_SSL", "True").lower() in ("true", "1", "yes")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "yes")

# Sender Branding & Signature Defaults
SENDER_NAME = os.getenv("SENDER_NAME", "Priyanshu Sharma (Founder & Head of Exports)")
SENDER_COMPANY = os.getenv("SENDER_COMPANY", "ResonaCraft Artisans Ltd.")
SENDER_CONTACT = os.getenv("SENDER_CONTACT", "+977-1-4412345 / +91-98765-43210 | export@resonacraft.com")
