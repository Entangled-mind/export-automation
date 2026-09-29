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
# Default to safe offline-seeded mode whenever no real search API credentials are configured.
# This keeps the app functional and prevents empty-result failures when the environment is not yet set up.
SEARCH_KEYWORD = os.getenv(
    "SEARCH_KEYWORD", "Himalayan singing bowls wholesale importer retailer"
)

# Search API credentials (used to decide whether live mode is available)
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", os.getenv("GOOGLE_SEARCH_API_KEY", ""))
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID", os.getenv("GOOGLE_CSE_ID", ""))
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "auto").lower()

_has_valid_live_search = bool((SEARCH_API_KEY and SEARCH_ENGINE_ID) or SERPAPI_API_KEY)
_test_mode_env = os.getenv("TEST_MODE")
if _test_mode_env is None:
    TEST_MODE = not _has_valid_live_search
else:
    TEST_MODE = _test_mode_env.lower() in ("true", "1", "yes")

# Data Quality Status Constants
STATUS_VALID = "VALID"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_INVALID_EMAIL = "INVALID_EMAIL"
STATUS_DUPLICATE = "DUPLICATE"
STATUS_REJECTED = "REJECTED"

# ==============================================================================
# SEARCH API SETTINGS (REAL-WORLD DISCOVERY)
# ==============================================================================

# General-purpose product presets for discovery. This list is intentionally broad enough
# to support product-selection UI with 100 quick-pick categories while still allowing
# arbitrary custom product searches in the live discovery workflow.
PRODUCT_SEARCH_PRESETS = [
    "Organic Coffee",
    "Organic Tea",
    "Yoga Mats",
    "Handmade Rugs",
    "Ceramic Mugs",
    "Pashmina Shawls",
    "Industrial Water Pumps",
    "Solar Equipment",
    "Home Textiles",
    "Kitchenware",
    "Packaging Supplies",
    "Wellness Products",
    "Bamboo Toothbrushes",
    "Natural Skincare",
    "Leather Bags",
    "Stainless Steel Bottles",
    "Recycled Paper Products",
    "Organic Cotton Apparel",
    "Essential Oils",
    "Scented Candles",
    "Travel Backpacks",
    "Portable Chargers",
    "Air Purifiers",
    "Water Filters",
    "Reusable Lunch Boxes",
    "Wooden Toys",
    "Decorative Lanterns",
    "Massage Oils",
    "Himalayan Salt Lamps",
    "Smart Home Devices",
    "Bamboo Kitchenware",
    "Herbal Teas",
    "Sustainable Stationery",
    "Glassware",
    "Plant-Based Protein",
    "Spice Blends",
    "Olive Oil",
    "Honey Products",
    "Coconut Products",
    "Indoor Plants",
    "Pet Accessories",
    "Ergonomic Chairs",
    "Fitness Bands",
    "Yoga Blocks",
    "Sustainable Apparel",
    "Linen Tablecloths",
    "Bath Towels",
    "Aromatherapy Diffusers",
    "Handmade Jewelry",
    "Sunglasses",
    "Beach Towels",
    "Office Organizers",
    "Cutlery Sets",
    "Mason Jars",
    "Reusable Grocery Bags",
    "Storage Bins",
    "Cleaning Supplies",
    "Wall Clocks",
    "Portable Fans",
    "Electric Kettles",
    "Mixing Bowls",
    "Cookware Sets",
    "Herbal Supplements",
    "Baby Care Products",
    "Natural Soaps",
    "Face Masks",
    "Hair Care Products",
    "Men's Grooming",
    "Women's Accessories",
    "Pet Food",
    "Pet Toys",
    "Garden Tools",
    "Planters",
    "Seed Kits",
    "Compost Bins",
    "Rain Barrels",
    "Solar Lights",
    "Portable Generators",
    "LED Bulbs",
    "Safety Gear",
    "Construction Tools",
    "Work Gloves",
    "Tool Storage",
    "Plastic Drums",
    "Agricultural Seeds",
    "Fertilizers",
    "Pest Control",
    "Greenhouse Supplies",
    "Packaging Films",
    "Shipping Boxes",
    "Protective Packaging",
    "Retail Displays",
    "Display Racks",
    "Warehouse Shelving",
    "Industrial Belts",
    "Pumps and Valves",
    "Electrical Components",
    "Cable Accessories",
    "Insulation Materials",
    "Rubber Seals",
    "Metal Fasteners",
    "Industrial Filters",
    "HVAC Parts",
    "Cooling Systems",
    "Heat Exchangers",
    "Medical Supplies",
    "Protective Wear",
    "Workwear Uniforms",
    "Automotive Parts",
    "Motorcycle Accessories",
]

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
SENDER_NAME = os.getenv("SENDER_NAME", "Operations Director")
SENDER_COMPANY = os.getenv("SENDER_COMPANY", "Export Commerce Studio")
SENDER_CONTACT = os.getenv("SENDER_CONTACT", "+1 (555) 010-2048 | export@exportcommerce.example")
