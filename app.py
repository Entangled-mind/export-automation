"""Streamlit Web Application for EXPORT Automation System (Dynamic B2B Lead Discovery).

Enables users to enter dynamic product keywords and optional countries to discover real,
publicly available B2B buyer leads across global export markets.

Features:
- Dynamic Product & Country Input (never hardcoded)
- Configurable Results Limit & Execution Mode (Production vs TEST_MODE)
- Real-Time Search Query Generation & Legitimate Search API querying
- Public Website Contact Extraction & Commercial Relevance Filter
- Comprehensive Data Quality Validation & Deduplication
- Enterprise SQLite Persistence (export_automation.db)
- Real-time KPI Metric Counters & Interactive Searchable Data Table
- One-Click CSV Export & Database Lead Explorer
"""

import io
import os
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

import config
from database.repository import (
    get_all_buyers,
    get_buyers_by_product,
    get_database_stats,
    get_recent_discovered_leads,
)
from database.schema import init_database
from search.lead_pipeline import run_discovery_pipeline
from search.query_generator import generate_buyer_queries
from search.search_api import ConfigurationRequiredError, SearchAPIAdapter
from outreach.email_sender import (
    save_email_credentials,
    send_single_email,
    test_smtp_credentials,
)
from outreach.template_manager import render_email_draft
from validation.email_validator import is_valid_email

# Page Configuration
st.set_page_config(
    page_title="B2B Lead Discovery Engine",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root { --ink:#172b3a; --muted:#627482; --line:#e3e9ec; --teal:#087e78; --paper:#f5f8f8; }
    html, body, [class*="css"] { font-family:'DM Sans', sans-serif; }
    .stApp { background:var(--paper); color:var(--ink); }
    [data-testid="stHeader"] { background:rgba(245,248,248,.92); }
    [data-testid="stSidebar"] { background:#102b3a; }
    [data-testid="stSidebar"] * { color:#edf5f5; }
    [data-testid="stSidebar"] [data-testid="stAlert"] * { color:#253a46; }
    .block-container { max-width:1440px; padding-top:2rem; padding-bottom:3rem; }
    .hero { position:relative; overflow:hidden; padding:2.25rem 2.5rem; margin-bottom:1.5rem; border-radius:22px; color:white; background:linear-gradient(115deg,#102b3a 0%,#174b55 60%,#087e78 100%); box-shadow:0 18px 40px rgba(16,43,58,.14); }
    .hero:after { content:''; position:absolute; width:270px; height:270px; right:7%; top:-155px; border:1px solid rgba(255,255,255,.18); border-radius:50%; box-shadow:0 0 0 28px rgba(255,255,255,.04),0 0 0 58px rgba(255,255,255,.035); }
    .hero-eyebrow { color:#a8e3d8; font-size:.76rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }
    .hero h1 { position:relative; z-index:1; margin:.55rem 0 .45rem; color:white; font:800 2.25rem/1.15 'Manrope',sans-serif; letter-spacing:-.04em; }
    .hero p { position:relative; z-index:1; max-width:680px; margin:0; color:#d5e4e5; font-size:1.02rem; line-height:1.6; }
    .hero-chip { display:inline-block; position:relative; z-index:1; margin-top:1.25rem; padding:.4rem .75rem; border:1px solid rgba(255,255,255,.24); border-radius:30px; color:#f1fffc; font-size:.8rem; }
    h2, h3 { font-family:'Manrope',sans-serif !important; letter-spacing:-.025em; color:var(--ink); }
    [data-testid="stTabs"] [role="tab"] { font-weight:600; }
    [data-testid="stTabs"] [aria-selected="true"] { color:var(--teal); }
    [data-testid="stForm"] { padding:1.35rem; border:1px solid var(--line); border-radius:16px; background:white; box-shadow:0 6px 20px rgba(16,43,58,.045); }
    [data-testid="stMetric"] { padding:1rem 1.1rem; border:1px solid var(--line); border-radius:14px; background:white; }
    [data-testid="stMetricLabel"] { color:var(--muted); font-weight:600; }
    [data-testid="stMetricValue"] { color:var(--ink); font-family:'Manrope',sans-serif; }
    .stButton > button[kind="primary"], .stFormSubmitButton > button { min-height:2.9rem; border:0; border-radius:10px; background:var(--teal); font-weight:700; }
    .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover { background:#066b66; border:0; }
    [data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:12px; overflow:hidden; }
    .section-kicker { margin:1.25rem 0 .35rem; color:var(--teal); font-size:.75rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }
    @media (max-width:720px) { .block-container { padding:1rem .8rem 2rem; } .hero { padding:1.5rem; border-radius:16px; } .hero h1 { font-size:1.7rem; } }
    .badge-live {
        background-color: #dcfce7;
        color: #166534;
        padding: 0.3rem 0.8rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .badge-test {
        background-color: #fef9c3;
        color: #854d0e;
        padding: 0.3rem 0.8rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.dialog("Send email")
def show_email_dialog(buyer: Dict[str, Any], lead_key: str) -> None:
    """Show a personalized draft and send it directly with 1 click."""
    draft = render_email_draft(buyer)
    st.caption("Review or edit this personalized buyer email before 1-click dispatch.")
    st.text_input("Recipient", value=draft.to_email, disabled=True, key=f"dialog_recipient_{lead_key}")
    subject = st.text_input("Subject", value=draft.subject, key=f"dialog_subject_{lead_key}")
    body_text = st.text_area("Message", value=draft.body_text, height=240, key=f"dialog_body_{lead_key}")

    has_configured_pwd = bool(
        config.GMAIL_APP_PASSWORD and config.GMAIL_APP_PASSWORD != "your_16_character_app_password"
    )

    if config.GMAIL_EMAIL and has_configured_pwd:
        st.markdown(f"**Connected Gmail:** `{config.GMAIL_EMAIL}` (Direct SSL)")
        if st.button("🚀 Send Email Now (1-Click)", type="primary", key=f"dialog_send_{lead_key}", use_container_width=True):
            with st.spinner(f"Dispatching live email to {draft.to_email}..."):
                result = send_single_email(
                    buyer,
                    dry_run=False,
                    test_mode=False,
                    subject_override=subject,
                    body_text_override=body_text,
                )
            if result.status == "SUCCESS":
                st.success(f"🎉 Email successfully delivered to {result.email}!")
                st.balloons()
                st.session_state.pop("active_email_lead", None)
                st.rerun()
            else:
                st.error(f"Dispatch failed: {result.message}")
                st.warning("You can also open the prepared message in your mail app:")
                mailto = f"mailto:{urllib.parse.quote(draft.to_email, safe='@.+-_')}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body_text)}"
                st.link_button("Open prepared email in mail app", mailto, use_container_width=True)
    else:
        st.warning(
            "⚠️ **Direct 1-Click Sending requires your 16-character Google App Password.**\n\n"
            "Please configure your App Password in the sidebar on the left to send emails instantly."
        )
        mailto = f"mailto:{urllib.parse.quote(draft.to_email, safe='@.+-_')}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body_text)}"
        st.link_button("Open prepared email in mail app", mailto, use_container_width=True)


def main():
    # Initialize the local persistence layer without inserting unrequested records.
    init_database()

    # Sidebar: System Controls & API Status
    st.sidebar.markdown(
        "<div style='padding:.7rem 0 1.25rem;border-bottom:1px solid #31505e;margin-bottom:1rem'>"
        "<div style='font-size:.72rem;letter-spacing:.15em;color:#91d7c9;font-weight:700'>EXPORT INTELLIGENCE</div>"
        "<div style='font:700 1.35rem Manrope,sans-serif;color:white;margin-top:.3rem'>Buyer Finder</div></div>",
        unsafe_allow_html=True,
    )
    # 1. EMAIL OUTREACH CONNECTION
    st.sidebar.markdown("### 📧 Email Outreach Connection")
    has_configured_pwd = bool(
        config.GMAIL_APP_PASSWORD and config.GMAIL_APP_PASSWORD != "your_16_character_app_password"
    )
    if has_configured_pwd:
        st.sidebar.success(f"✅ Connected: `{config.GMAIL_EMAIL}`")
    else:
        st.sidebar.warning("⚠️ Google App Password required for 1-click direct sending.")

    with st.sidebar.expander("⚙️ Connect Gmail Account", expanded=not has_configured_pwd):
        sb_email = st.text_input("Gmail Address", value=config.GMAIL_EMAIL or "priy2909@gmail.com", key="sb_email_in")
        sb_pwd = st.text_input(
            "16-char App Password",
            value="" if config.GMAIL_APP_PASSWORD == "your_16_character_app_password" else config.GMAIL_APP_PASSWORD,
            type="password",
            placeholder="abcd efgh ijkl mnop",
            help="16-character Google App Password from myaccount.google.com/apppasswords",
            key="sb_pwd_in",
        )
        sb_sender = st.text_input("Sender Name", value=config.SENDER_NAME or "Export Manager", key="sb_sender_in")
        sb_comp = st.text_input("Company Name", value=config.SENDER_COMPANY or "Global Exports", key="sb_comp_in")

        if st.button("🔌 Connect & Test Gmail", use_container_width=True, type="primary"):
            if not sb_email.strip() or not sb_pwd.strip():
                st.error("Please provide both your Gmail address and 16-character App Password.")
            else:
                with st.spinner("Authenticating with Gmail SMTP..."):
                    ok, msg = test_smtp_credentials(email=sb_email, password=sb_pwd)
                if ok:
                    save_email_credentials(
                        email=sb_email,
                        password=sb_pwd,
                        sender_name=sb_sender,
                        sender_company=sb_comp,
                    )
                    st.success(f"🎉 Connected! {msg}")
                    st.rerun()
                else:
                    st.error(msg)

        st.caption(
            "👉 **[Get 16-Character App Password](https://myaccount.google.com/apppasswords)**\n\n"
            "1. Turn on 2-Step Verification in Google Account.\n"
            "2. Visit `myaccount.google.com/apppasswords`.\n"
            "3. Generate an App Password named 'Export Automation'.\n"
            "4. Paste the 16 characters above."
        )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Search Mode")

    # Mode Selector
    search_adapter = SearchAPIAdapter()
    has_api_keys = bool(config.SEARCH_API_KEY and config.SEARCH_ENGINE_ID) or bool(config.SERPAPI_API_KEY)

    test_mode_toggle = st.sidebar.toggle(
        "Run in TEST_MODE (Offline Fixtures)",
        value=False,
        help="Development-only mode. Live discovery searches the public web across any product category.",
    )

    if test_mode_toggle:
        st.sidebar.markdown(
            '<div class="badge-test">TEST MODE • Offline fixtures</div>',
            unsafe_allow_html=True,
        )
        st.sidebar.info("Offline fixtures only. No live external search queries are made.")
    else:
        st.sidebar.markdown(
            '<div class="badge-live">LIVE MODE: Universal Buyer Search</div>',
            unsafe_allow_html=True,
        )
        if has_api_keys:
            st.sidebar.caption("Search Engine: Google Custom Search / SerpAPI")
        else:
            st.sidebar.caption("Search Engine: Live Public Web Search (Zero setup required)")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Data Sources")
    st.sidebar.markdown(
        "Public company websites, real-time web search results, and extracted commercial business contacts."
    )

    # Main Header
    st.markdown(
        '<div class="hero"><div class="hero-eyebrow">Export intelligence workspace</div>'
        '<h1>Find the right buyers.<br>Build your next market.</h1>'
        '<p>Research public business sources to discover importers, distributors and wholesale partners for ANY product.</p>'
        '<span class="hero-chip">Universal buyer discovery &nbsp;•&nbsp; 1-click email outreach &nbsp;•&nbsp; Lead catalog</span></div>',
        unsafe_allow_html=True,
    )

    # Top Notice if in TEST_MODE vs LIVE MODE
    if test_mode_toggle:
        st.warning(
            "⚠️ **Notice: TEST_MODE is currently ACTIVE.** "
            "Offline fixtures are used. Toggle off in the sidebar for real-time live discovery."
        )

    # Tabs: 1. Lead Discovery Engine | 2. Database Catalog Explorer
    tab_discovery, tab_catalog = st.tabs(["Buyer discovery", "Lead catalog"])

    with tab_discovery:
        # User Input Form (Section 1)
        st.markdown('<div class="section-kicker">01 &nbsp; Market research</div>', unsafe_allow_html=True)
        st.subheader("Set your buyer profile")
        with st.form("lead_discovery_form"):
            product_categories = [
                "Custom / Enter Any Product Below",
                "Shoes & Footwear",
                "Coffee & Tea",
                "Solar Panels & Green Energy",
                "Apparel & Garments",
                "Home Decor & Furniture",
                "Handmade Rugs & Carpets",
                "Jewelry & Gemstones",
                "Cosmetics & Skincare",
                "Bicycles & Sporting Goods",
                "Electronics & Gadgets",
                "Packaging & Paper Goods",
                "Organic Spices & Food Ingredients",
                "Ceramics & Tableware",
                "Leather Goods & Bags",
                "Industrial Hardware & Tools",
                "Singing Bowls & Wellness",
            ]
            countries = [
                "Any country", "United States", "United Kingdom", "Canada", "Australia",
                "Germany", "France", "Netherlands", "Italy", "Spain", "Switzerland",
                "Austria", "Sweden", "Norway", "Denmark", "Belgium", "Ireland",
                "Japan", "South Korea", "Singapore", "United Arab Emirates", "Saudi Arabia",
                "India", "Nepal", "New Zealand", "South Africa", "Brazil", "Mexico",
                "Other / custom country",
            ]
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                product_choice = st.selectbox(
                    "Product category *", product_categories, index=0,
                    help="Choose a category or type any specific product below.",
                )
                default_prod_text = "" if product_choice.startswith("Custom") else product_choice.split(" & ")[0]
                custom_product = st.text_input(
                    "Target product or keyword *",
                    value=default_prod_text,
                    placeholder="e.g. Shoes, Coffee, Solar Panels, Bicycles, Wine, Jewelry...",
                    key="custom_product",
                    help="Enter ANY product keyword to discover commercial importers and wholesalers worldwide.",
                )
                product_input = custom_product.strip() or ("" if product_choice.startswith("Custom") else product_choice)
            with col2:
                country_choice = st.selectbox(
                    "Target country", countries, index=0,
                    help="Choose a country from the list, or select Any country.",
                )
                custom_country = st.text_input("Or enter another country (optional)", placeholder="Type a country not listed", key="custom_country")
                country_input = custom_country.strip() or ("" if country_choice in {"Any country", "Other / custom country"} else country_choice)
            with col3:
                max_results_input = st.slider(
                    "Maximum Results",
                    min_value=5,
                    max_value=50,
                    value=20,
                    step=5,
                    help="Number of target buyer leads to discover.",
                )

            col4, col5 = st.columns(2)
            with col4:
                region_input = st.text_input(
                    "Target Region (Optional)",
                    value="",
                    placeholder="e.g. California, Bavaria, Gujarat",
                    help="Narrow discovery to a city, state, or regional market.",
                )
            with col5:
                buyer_type_input = st.selectbox(
                    "Buyer Type (Optional)",
                    ["Any", "Importer", "Distributor", "Wholesaler", "Retailer", "Manufacturer", "Dealer", "Sourcing Company", "Trading Company", "Other"],
                    index=0,
                )

            additional_context = st.text_area(
                "Additional Search Context (Optional)",
                value="",
                placeholder="Looking for businesses that source this product for resale.",
                help="Use this to refine the search strategy for the exact buyer profile you want.",
            )

            submitted = st.form_submit_button("🔍 Find matching buyers", type="primary", use_container_width=True)

        # Handle Pipeline Execution
        if submitted:
            clean_prod = product_input.strip()
            if not clean_prod:
                st.error("Please enter a valid product or keyword to search for.")
            else:
                progress_container = st.container()
                with progress_container:
                    status_text = st.empty()
                    progress_bar = st.progress(0.1)

                    try:
                        status_text.info(f"Generating buyer-intent search queries for '{clean_prod}'...")
                        progress_bar.progress(0.25)

                        status_text.info(f"Querying search engine and discovering companies for '{clean_prod}'...")
                        progress_bar.progress(0.50)

                        # Run Pipeline with universal public search fallback
                        discovery_results = run_discovery_pipeline(
                            product=clean_prod,
                            country=country_input.strip() or None,
                            region=region_input.strip() or None,
                            buyer_type=(None if buyer_type_input == "Any" else buyer_type_input),
                            additional_context=additional_context.strip() or None,
                            max_results=max_results_input,
                            test_mode=test_mode_toggle,
                            save_to_db=True,
                            allow_public_fallback=True,
                        )

                        progress_bar.progress(1.0)
                        if discovery_results.get("errors") and not discovery_results.get("raw_results_count"):
                            status_text.warning("Search returned no pages. See the diagnostics below.")
                        else:
                            status_text.success(f"Discovery complete for '{clean_prod}'.")

                        # Store in session state for persistence during interaction
                        st.session_state["latest_discovery"] = discovery_results

                    except ConfigurationRequiredError as cfg_err:
                        progress_bar.empty()
                        status_text.error(str(cfg_err))
                        st.stop()
                    except Exception as err:
                        progress_bar.empty()
                        status_text.error(f"Pipeline error: {err}")
                        st.stop()

        # Display Latest Discovery Results
        if "latest_discovery" in st.session_state:
            data = st.session_state["latest_discovery"]
            st.markdown("---")
            st.subheader(f"Results for Product: '{data['product']}' (Market: {data['country']})")

            leads = [
                lead for lead in data.get("leads", [])
                if lead.get("validation_status") != config.STATUS_REJECTED
            ]
            catalog_fallback = bool(data.get("catalog_fallback"))
            if not leads and not catalog_fallback:
                saved_matches = get_buyers_by_product(data.get("product", ""))
                wanted_country = (data.get("country") or "").strip().lower()
                country_aliases = {"usa": "united states", "us": "united states", "united states of america": "united states"}
                wanted_country = country_aliases.get(wanted_country, wanted_country)
                leads = [
                    lead for lead in saved_matches
                    if lead.get("validation_status") != config.STATUS_REJECTED
                    and (not wanted_country or wanted_country == "all" or country_aliases.get((lead.get("country") or "").strip().lower(), (lead.get("country") or "").strip().lower()) == wanted_country)
                ]
                catalog_fallback = bool(leads)
            if leads:
                if catalog_fallback:
                    st.info(f"Live search found no new results. Showing {len(leads)} matching public-source prospects already saved in your catalog.")
                    st.markdown("### Saved buyer prospects")
                else:
                    st.markdown("### Buyer matches")
                st.caption("Publicly listed contact details are shown with the source website. Emails are extracted from public pages and are not inbox-verified.")
                table_rows = []
                for lead_index, lead in enumerate(leads):
                    company = lead.get("company_name") or "Business listing"
                    email = (lead.get("email") or "").strip()
                    website = (lead.get("website") or "").strip()
                    country = lead.get("country") or ""
                    email_found = bool(email and is_valid_email(email) and lead.get("validation_status") != config.STATUS_REJECTED)
                    table_rows.append({
                        "Company": company,
                        "Contact": lead.get("buyer_name") or "Not listed",
                        "Email": email or "Not publicly listed",
                        "Website": website or "Not available",
                        "Source": lead.get("contact_source_url") or lead.get("source_url") or website,
                        "Country": country or "Not verified",
                        "Product": lead.get("product") or data.get("product", ""),
                        "Status": "Public email found" if email_found else "Website found; contact needs review",
                    })
                    with st.container(border=True):
                        left, right = st.columns([4, 1])
                        with left:
                            st.markdown(f"#### {company}")
                            st.caption(" • ".join(part for part in [country or "Country not verified", lead.get("product") or data.get("product", "") ] if part))
                            if email_found:
                                st.markdown(f"**Public email:** [{email}](mailto:{urllib.parse.quote(email, safe='@.+-_')})")
                                source_note = lead.get("email_source") or "Found on the business website"
                                st.caption(f"{source_note}; delivery is not guaranteed.")
                            else:
                                st.markdown("**Public email:** Not found or not verified")
                            contact_source = lead.get("contact_source_url") or lead.get("source_url") or website
                            if contact_source:
                                st.markdown(f"[View source page]({contact_source})")
                        with right:
                            if website.startswith(("https://", "http://")):
                                st.link_button("Visit website", website, use_container_width=True)
                            if email_found and not test_mode_toggle:
                                if st.button("⚡ Send Email (1-Click)", key=f"open_email_{lead_index}", use_container_width=True, type="primary"):
                                    st.session_state["active_email_lead"] = (lead_index, lead)
                                    st.rerun()
                    active_email = st.session_state.get("active_email_lead")
                    if active_email and active_email[0] == lead_index:
                        show_email_dialog(active_email[1], f"{data.get('product', 'lead')}_{lead_index}")
                df = pd.DataFrame(table_rows)

                # CSV Download Button
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="📥 Download Discovered Leads (CSV)",
                    data=csv_buffer.getvalue(),
                    file_name=f"discovered_leads_{data['product'].replace(' ', '_').lower()}.csv",
                    mime="text/csv",
                )

                # Transparency & Manual Review: Search Queries & URLs (Section 5 & 13)
                with st.expander("🔎 View Generated Search Queries & Transparency Log"):
                    st.write("**Search Queries Used:**")
                    for q in data.get("queries", []):
                        st.code(q, language="text")

                    if data.get("errors"):
                        st.write("**Non-fatal Processing Warnings:**")
                        for err in data.get("errors", []):
                            st.caption(f"• {err}")
            else:
                if data.get("errors"):
                    st.error(
                        "The search or website lookup failed, so no buyers could be confirmed. "
                        "Check the search provider configuration and try again."
                    )
                    for err in data["errors"]:
                        st.caption(err)
                else:
                    st.info(
                        "No matching buyers were confirmed. Try a shorter product term, choose a target country, "
                        "or configure Google Custom Search / SerpAPI if live search is using the public fallback."
                    )

    with tab_catalog:
        st.subheader("🗄️ Enterprise SQLite Master Catalog (export_automation.db)")
        all_buyers = get_all_buyers()
        stats = get_database_stats()

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total Cataloged Leads", stats.get("total_buyers", len(all_buyers)))
        col_b.metric("B2B Wholesale Accounts", stats.get("business_buyers", 0))
        col_c.metric("Active Outreach Dispatches", stats.get("outreach_success", 0) + stats.get("outreach_simulated", 0))

        # Filter by Product in Database
        filter_product = st.text_input("Filter Catalog by Product", placeholder="e.g. Singing Bowls, Yoga Mats")
        if filter_product.strip():
            filtered_buyers = get_buyers_by_product(filter_product.strip())
        else:
            filtered_buyers = all_buyers

        if filtered_buyers:
            cat_df = pd.DataFrame(filtered_buyers)[
                [col for col in ["company_name", "buyer_name", "email", "product", "country", "website", "quality_status", "source_url"] if col in pd.DataFrame(filtered_buyers).columns]
            ]
            cat_df.columns = [c.replace("_", " ").title() for c in cat_df.columns]
            cat_df = cat_df.replace(r"^\s*$", "N/A", regex=True)
            st.dataframe(cat_df, use_container_width=True)
        else:
            st.info("No buyers found matching filter.")

        # All valid buyer contacts in SQLite can be emailed directly from here
        researched_leads = [
            buyer for buyer in all_buyers
            if is_valid_email(buyer.get("email") or "")
            and buyer.get("validation_status") != config.STATUS_REJECTED
        ]
        st.markdown("### 📧 Email a Catalog Buyer")
        has_configured_pwd = bool(
            config.GMAIL_APP_PASSWORD and config.GMAIL_APP_PASSWORD != "your_16_character_app_password"
        )
        if test_mode_toggle:
            st.info("Email sending is disabled in offline TEST_MODE.")
        elif not config.GMAIL_EMAIL or not has_configured_pwd:
            st.warning("⚠️ Enter your 16-character Google App Password in the sidebar on the left to enable 1-click email sending.")
        elif not researched_leads:
            st.info("No buyer contacts with verified emails found in catalog.")
        else:
            research_choices = {
                f"{buyer.get('company_name') or 'Unknown company'} — {buyer['email']} ({buyer.get('product') or 'General'})": buyer
                for buyer in researched_leads
            }
            research_label = st.selectbox(
                "Select a buyer lead to contact", list(research_choices), key="catalog_researched_buyer"
            )
            research_buyer = research_choices[research_label]
            research_draft = render_email_draft(research_buyer)
            st.caption(f"Connected sender: **{config.GMAIL_EMAIL}** (Direct SSL port 465). Review draft before sending.")
            research_subject = st.text_input(
                "Subject", value=research_draft.subject,
                key=f"catalog_subject_{research_draft.to_email}",
            )
            research_body = st.text_area(
                "Message", value=research_draft.body_text, height=240,
                key=f"catalog_body_{research_draft.to_email}",
            )
            if research_draft.attachment_path:
                st.caption(f"📎 Catalog attachment: {research_draft.attachment_path.name}")
            if st.button(
                f"🚀 Send 1-Click Email to {research_buyer.get('company_name') or research_draft.to_email}",
                type="primary", key=f"catalog_send_{research_draft.to_email}", use_container_width=True,
            ):
                with st.spinner(f"Dispatching live email to {research_draft.to_email}..."):
                    send_result = send_single_email(
                        research_buyer,
                        dry_run=False,
                        test_mode=False,
                        subject_override=research_subject,
                        body_text_override=research_body,
                    )
                if send_result.status == "SUCCESS":
                    st.success(f"🎉 Email successfully dispatched to {send_result.email} via {config.GMAIL_EMAIL}!")
                    st.balloons()
                else:
                    st.error(f"Email {send_result.status.lower().replace('_', ' ')}: {send_result.message}")
                    st.warning("The SMTP server did not accept this email, so it was not sent. You can open the prepared message in your mail app and send it there.")
                    mailto = f"mailto:{urllib.parse.quote(research_draft.to_email, safe='@.+-_')}?subject={urllib.parse.quote(research_subject)}&body={urllib.parse.quote(research_body)}"
                    st.link_button("Open prepared email in mail app", mailto, use_container_width=True)


if __name__ == "__main__":
    main()
