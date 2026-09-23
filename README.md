# EXPORT Automation System — API 3 (Singing Bowls Export Business)

> **Phases 1 & 2: Complete Local Foundation, Lead Discovery & AI Classification**

The **EXPORT Automation System** is designed for a Singing Bowls export business to discover international buyers, normalize and validate contact data, prevent duplicates, intelligently classify contacts into B2B businesses vs B2C individuals with AI, and prepare targeted wholesale outreach.

---

## 📌 Architecture & Implemented Pipeline

```text
[Phase 2] Buyer Discovery (Search Adapters / Directories / Portals)
       ↓
[Phase 2] Raw Contact Leads Extraction
       ↓
[Phase 1] Data Normalization & Sanitization (data_extractor.py)
       ↓
[Phase 1] Email Syntax Validation (email_validator.py)
       ↓
[Phase 1] Duplicate Prevention (Discovery & Prior Sent History)
       ↓
[Phase 1] Master Catalog Storage (data/buyers.csv)
       ↓
[Phase 2] AI Classification (Google Gemini / Heuristic Engine)
       ↓
[Phase 2] Contact Segregation:
          ├── data/business_buyers.csv   (B2B: Wholesalers, Studios, Spas, Importers)
          └── data/individual_buyers.csv (B2C: Personal buyers, Yoga practitioners)
       ↓
[Phase 3] Outreach Engine (Upcoming: Rate-limited Gmail outreach with PDF presentation attachment)
```

---

## 🎯 What Phase 1 & Phase 2 Accomplish

### Phase 1: Core Foundation & Data Infrastructure
1. **Standardized Project Structure**: Modular, beginner-friendly architecture.
2. **Centralized Configuration**: Settings loaded safely from `.env` using `python-dotenv`.
3. **Data Normalization**: Cleans whitespace, lowercases emails, and safely handles missing fields.
4. **Email Syntax Validation**: Validates structure without making intrusive SMTP network calls.
5. **Two-Tier Duplicate Detection**:
   - Skips contacts already in `data/buyers.csv`.
   - Skips contacts who previously received successful outreach in `data/sent_log.csv`.
6. **Activity & Sent Auditing**: Full traceability in `data/activity_log.csv` and `data/sent_log.csv`.

### Phase 2: Buyer Discovery & AI Classification
1. **Search Adapters (`discovery/search_adapter.py`)**:
   - Discovers potential Singing Bowls buyer leads across global markets (USA, UK, Germany, Canada, Australia, India).
   - Includes HTML directory parser and offline demo dataset for 100% reliable demos and tests.
2. **AI Classification Engine (`classification/classifier.py`)**:
   - **Google Gemini Mode**: Uses Gemini API when `GEMINI_API_KEY` is provided in `.env`.
   - **Explainable Heuristic Fallback**: Zero-dependency rule engine that evaluates corporate entity suffixes (`GmbH`, `Ltd`, `Wholesale`, `Studio`), dedicated business web domains, and freemail flags.
3. **Contact Segregation**:
   - Saves priority B2B export targets into `data/business_buyers.csv`.
   - Saves consumer/retail contacts into `data/individual_buyers.csv`.
   - Appends detailed classification rationale (`reasoning`) to every record.

---

## 🚫 What is Saved for Phase 3

- **NO real emails sent yet**: Gmail SMTP connection and sending are Phase 3 features.
- **NO PDF attachments dispatched**: PDF presentation attachment will be automated during Phase 3 outreach.

---

## 📁 Project Structure

```text
export-automation/
│
├── main.py                     # Runs end-to-end Phase 2 discovery & classification pipeline
├── config.py                   # Central settings, paths, and environment loader
├── requirements.txt            # Minimal project dependencies
├── .env                        # Local environment variables
├── .env.example                # Example environment template
├── .gitignore                  # Git ignore rules
├── README.md                   # Complete beginner guide & interview walkthrough
│
├── discovery/                  # [Phase 2] Lead search & discovery adapters
│   ├── __init__.py
│   └── search_adapter.py       # Searches Singing Bowls leads & parses directories
│
├── classification/             # [Phase 2] AI buyer classification
│   ├── __init__.py
│   └── classifier.py           # Gemini AI classifier with intelligent heuristic fallback
│
├── extraction/                 # Data normalization & CSV storage
│   ├── __init__.py
│   └── data_extractor.py       # Normalizes data and manages all buyer CSVs
│
├── validation/                 # Email syntax & outreach duplicate screening
│   ├── __init__.py
│   └── email_validator.py      # Validates email format & duplicate logic
│
├── logging_module/             # Activity & sent-history tracking
│   ├── __init__.py
│   └── activity_logger.py      # Logs activity & manages data/sent_log.csv
│
├── data/                       # Persistent CSV databases
│   ├── buyers.csv              # Master catalog of all unique, valid buyers
│   ├── business_buyers.csv     # B2B export leads (wholesalers, studios, importers)
│   ├── individual_buyers.csv   # B2C consumer / hobbyist contacts
│   ├── sent_log.csv            # Outreach history and send statuses
│   └── activity_log.csv        # Detailed execution audit trail
│
├── tests/                      # Automated test suite (16 unit tests)
│   ├── __init__.py
│   ├── test_phase1.py          # Phase 1 unit tests (normalization, validation, CSVs)
│   └── test_phase2.py          # Phase 2 unit tests (discovery, AI classifier, segregation)
│
└── assets/                     # Presentation attachments & assets
    └── .gitkeep
```

---

## 🛠️ Step-by-Step Setup

### 1. Prerequisites
- **Python 3.10+**

### 2. Create and Activate Virtual Environment
```powershell
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Optional: Add Gemini API Key
If you want to use Google Gemini AI for classification, add your key to `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```
*(If left blank, the system automatically runs the built-in heuristic classifier without any errors).*

---

## 🚀 Running the Program

Run the automated pipeline:
```powershell
python main.py
```

### Example Terminal Output:
```text
=================================================================
EXPORT Automation System - Phase 2 (Discovery & AI Pipeline)
Target Product : Singing Bowls wholesale imports studio
Data Directory : ...\export-automation\data
Classify Engine: Heuristic Rule Engine (Offline/Zero-Key)
=================================================================
[2026-09-18T19:29:23] [SYSTEM_INIT] INFO: Initialized CSV databases.

[Step 1] Discovering potential Singing Bowls buyer leads...
-> Discovered 9 prospective raw leads from search/directory adapters.

--- Processing & Classifying Leads ---
[2026-09-18T19:29:23] [BUYER_CATALOGED] [contact@soundsanctuary.com] SUCCESS: Saved to master catalog: Maya Lin (Sound Sanctuary Studio)
[2026-09-18T19:29:23] [AI_CLASSIFICATION] [contact@soundsanctuary.com] BUSINESS: [Heuristic] Strong commercial indicators in company name ('Sound Sanctuary Studio').
[2026-09-18T19:29:23] [BUYER_CATALOGED] [purchasing@himalayan-sound.de] SUCCESS: Saved to master catalog: Klaus Weber (Himalayan Art & Sound GmbH)
[2026-09-18T19:29:23] [AI_CLASSIFICATION] [purchasing@himalayan-sound.de] BUSINESS: [Heuristic] Strong commercial indicators in company name ('Himalayan Art & Sound GmbH').
...
[2026-09-18T19:29:24] [EMAIL_VALIDATION] [invalid@contact@nowhere] REJECTED: Invalid email syntax.

=======================================================
EXPORT AUTOMATION SYSTEM - PHASE 2 SUMMARY
=======================================================
Raw leads discovered         : 9
Valid emails verified        : 8
Invalid emails rejected      : 1
New buyers added to catalog  : 8
Duplicate leads skipped      : 0
Prior sent emails skipped    : 0
-------------------------------------------------------
Classified as BUSINESS (B2B) : 6 -> data/business_buyers.csv
Classified as INDIVIDUAL(B2C): 2 -> data/individual_buyers.csv
=======================================================
Phase 2 pipeline completed successfully.
```

---

## 🧪 Running Unit Tests

Run all 16 automated tests across Phase 1 and Phase 2:
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

All tests run in sandboxed temporary folders without modifying your production `data/` files.

---

## 🎓 How to Explain Phase 2 in an Internship Interview

1. **Architecture Modularity**:
   > *"I designed the system in clean, decoupled modules. The discovery adapter feeds untrusted raw leads into our Phase 1 normalization and validation layer, and only verified, non-duplicate contacts reach the AI classification engine."*
2. **AI Classification with Graceful Fallback**:
   > *"For classifying B2B vs B2C leads, I integrated Google Gemini AI. However, to guarantee 100% system reliability and offline testability, I implemented an intelligent heuristic fallback that inspects corporate suffixes, registered domains, and freemail flags."*
3. **Data Segregation for High-Value Outreach**:
   > *"Wholesale export outreach requires different messaging than retail inquiries. By automatically segregating leads into `business_buyers.csv` and `individual_buyers.csv`, Phase 3 can focus high-volume wholesale pitch decks on verified commercial buyers."*
