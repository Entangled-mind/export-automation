"""Email template management and dynamic personalization module for Phase 4 outreach.

Specialized for Himalayan Singing Bowls export products:
- Tier 1: Wholesale Importers & Bulk Distributors
- Tier 2: Sound Healing Studios, Spas, and Wellness Academies
- Tier 3: Solo Practitioners & Boutique Retailers

Provides both Plain Text and HTML MIME templates with robust placeholder fallbacks.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import config


@dataclass
class EmailDraft:
    """Represents a fully composed, personalized email ready for dispatch."""

    to_email: str
    to_name: str
    company_name: str
    subject: str
    body_text: str
    body_html: str
    attachment_path: Optional[Path] = None


# ==============================================================================
# DEFAULT SUBJECTS & PITCHES
# ==============================================================================
DEFAULT_TIER1_ANGLE = (
    "Direct Himalayan Export: Artisan Hand-Hammered 7-Metals Singing Bowls with Wholesale Volume Pricing."
)
DEFAULT_TIER2_ANGLE = (
    "Master-Grade 7-Chakra Tuned Singing Bowl Sets & Meditation Gongs tailored for sound baths and therapy sessions."
)
DEFAULT_TIER3_ANGLE = (
    "Handcrafted Himalayan Singing Bowl Starter Kits with Felt Mallet & Brocade Cushion for Personal Practice."
)


def get_personalized_placeholders(buyer: Dict[str, str]) -> Dict[str, str]:
    """Extract and sanitize personalized placeholders with graceful fallbacks.

    Args:
        buyer: Normalized buyer dictionary.

    Returns:
        Dictionary of formatted placeholder strings.
    """
    raw_name = (buyer.get("buyer_name") or "").strip()
    raw_company = (buyer.get("company_name") or "").strip()
    raw_country = (buyer.get("country") or "").strip()
    raw_angle = (buyer.get("outreach_angle") or "").strip()
    raw_tier = (buyer.get("tier") or "").strip()

    # Graceful salutation fallback
    salutation = raw_name if raw_name else (f"Team at {raw_company}" if raw_company else "Purchasing Team")
    company_display = raw_company if raw_company else "your esteemed organization"
    country_display = f" in {raw_country}" if raw_country else ""

    if not raw_angle:
        if config.TIER_1 in raw_tier:
            raw_angle = DEFAULT_TIER1_ANGLE
        elif config.TIER_2 in raw_tier:
            raw_angle = DEFAULT_TIER2_ANGLE
        else:
            raw_angle = DEFAULT_TIER3_ANGLE

    return {
        "salutation": salutation,
        "company_name": company_display,
        "raw_company": raw_company,
        "country": country_display,
        "outreach_angle": raw_angle,
        "sender_name": config.SENDER_NAME,
        "sender_company": config.SENDER_COMPANY,
        "sender_contact": config.SENDER_CONTACT,
    }


# ==============================================================================
# TIER 1 TEMPLATES (WHOLESALE / DISTRIBUTORS)
# ==============================================================================
def render_tier1_content(p: Dict[str, str]) -> Dict[str, str]:
    """Render Tier 1 wholesale outreach copy."""
    company_title = f" -- {p['raw_company']}" if p["raw_company"] else ""
    subject = f"Direct Wholesale Himalayan Singing Bowls Export{company_title}"

    body_text = f"""Dear {p['salutation']},

Greetings from {p['sender_company']}.

We specialize in direct artisan export of authentic hand-hammered Himalayan Singing Bowls, cast from the traditional 7-metals alloy (Gold, Silver, Copper, Iron, Tin, Lead, and Zinc) in the foothills of the Himalayas.

We noted your leading position{p['country']} and would like to propose a direct B2B partnership:
-> Strategic Focus: {p['outreach_angle']}
-> Direct Factory/Artisan Container & Pallet Pricing (30-45% below European/US middleman distributors)
-> Custom Laser Engraving, Private Labeling, and Custom Wooden Boxes
-> Verified 432Hz & 440Hz Master Acoustic Tuning with Quality Certification

Attached please find our official Export Catalog & Company Presentation PDF detailing container volume tiers, product specs, and international freight logistics.

Would you be open to receiving a curated physical sample set or a 10-minute introductory call next week?

Warm regards,

{p['sender_name']}
International B2B Trade Division
{p['sender_company']}
{p['sender_contact']}
"""

    body_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #222; }}
    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
    .header {{ border-bottom: 2px solid #8B5CF6; padding-bottom: 12px; margin-bottom: 20px; }}
    .title {{ font-size: 20px; color: #1e1b4b; font-weight: 700; margin: 0; }}
    .badge {{ display: inline-block; background: #ede9fe; color: #6d28d9; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; margin-top: 6px; }}
    .highlight-box {{ background: #f8fafc; border-left: 4px solid #8B5CF6; padding: 14px 18px; margin: 18px 0; border-radius: 4px; }}
    .specs-list {{ margin: 14px 0; padding-left: 20px; }}
    .specs-list li {{ margin-bottom: 8px; }}
    .footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h2 class="title">Himalayan Artisan Singing Bowls Export Guild</h2>
      <span class="badge">Official B2B Wholesale Export</span>
    </div>
    <p>Dear <strong>{p['salutation']}</strong>,</p>
    <p>Greetings from <strong>{p['sender_company']}</strong>.</p>
    <p>We are a direct artisan exporter of authentic hand-hammered Himalayan Singing Bowls crafted from the traditional 7-metals alloy in the foothills of the Himalayas.</p>
    
    <div class="highlight-box">
      <strong>Recommended Partnership Focus:</strong><br>
      {p['outreach_angle']}
    </div>

    <p>Key wholesale benefits for {p['company_name']}:</p>
    <ul class="specs-list">
      <li><strong>Direct Origin Pricing:</strong> 30% to 45% below Western middleman distributors.</li>
      <li><strong>Master Acoustic Tuning:</strong> Precision 432Hz &amp; 440Hz concert tuning verified before shipment.</li>
      <li><strong>Private Label &amp; OEM:</strong> Custom laser engraving, artisan story cards, and custom gift boxes.</li>
      <li><strong>Verified Composition:</strong> Authenticity certificates for traditional 7-metals bell bronze.</li>
    </ul>

    <p>Attached to this email is our full <strong>Export Catalog &amp; Company Presentation PDF</strong> including wholesale tier schedules, pallet specifications, and lead times.</p>

    <p>Would you be open to receiving a physical sample set or scheduling a brief 10-minute introductory call next week?</p>

    <div class="footer">
      <p>Warm regards,<br>
      <strong>{p['sender_name']}</strong><br>
      International Trade Director | {p['sender_company']}<br>
      {p['sender_contact']}</p>
    </div>
  </div>
</body>
</html>
"""
    return {"subject": subject, "body_text": body_text, "body_html": body_html}


# ==============================================================================
# TIER 2 TEMPLATES (STUDIOS & SPAS)
# ==============================================================================
def render_tier2_content(p: Dict[str, str]) -> Dict[str, str]:
    """Render Tier 2 studio and wellness center outreach copy."""
    subject = f"Master-Grade 7-Chakra Singing Bowl Sets for {p['company_name']}"

    body_text = f"""Dear {p['salutation']},

Greetings from {p['sender_company']}.

We love the sound therapy and wellness work you do at {p['company_name']}. 

We hand-craft artisan 7-Metals Tibetan Singing Bowls specifically tuned for sound healers, yoga masters, and spa practitioners:
-> Focus: {p['outreach_angle']}
-> Exact Chakra Frequencies (Root to Crown: C, D, E, F, G, A, B)
-> Rich Harmonic Overtones & Sustained Resonance (over 60+ seconds resonance decay)
-> Complete Studio Sets including Suede Strikers, Wool Mallets, and Brocade Ring Cushions

We supply wellness studios worldwide directly from our Kathmandu artisan workshop, eliminating retail markups.

Attached is our Studio Catalog Presentation PDF showcasing our concert-grade sound bath sets and artisan bells.

May we send you an acoustic audio preview or discuss a tailored studio starter set?

In harmony,

{p['sender_name']}
Artisan Sound Specialist
{p['sender_company']}
{p['sender_contact']}
"""

    body_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #222; }}
    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
    .header {{ border-bottom: 2px solid #10B981; padding-bottom: 12px; margin-bottom: 20px; }}
    .title {{ font-size: 20px; color: #064e3b; font-weight: 700; margin: 0; }}
    .badge {{ display: inline-block; background: #d1fae5; color: #047857; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; margin-top: 6px; }}
    .highlight-box {{ background: #f0fdf4; border-left: 4px solid #10B981; padding: 14px 18px; margin: 18px 0; border-radius: 4px; }}
    .specs-list {{ margin: 14px 0; padding-left: 20px; }}
    .specs-list li {{ margin-bottom: 8px; }}
    .footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h2 class="title">Himalayan Artisan Singing Bowls</h2>
      <span class="badge">Master-Grade Sound Therapy Sets</span>
    </div>
    <p>Dear <strong>{p['salutation']}</strong>,</p>
    <p>Greetings from <strong>{p['sender_company']}</strong>. We admire the sound therapy and wellness work you do at {p['company_name']}.</p>
    
    <div class="highlight-box">
      <strong>Tailored Studio Focus:</strong><br>
      {p['outreach_angle']}
    </div>

    <p>Why sound practitioners choose our artisan bowls:</p>
    <ul class="specs-list">
      <li><strong>Precision 7-Chakra Tuning:</strong> Exact frequency calibration from Root (C) to Crown (B).</li>
      <li><strong>Long Resonance Decay:</strong> Hand-hammered bell bronze delivering 60+ seconds sustained vibration.</li>
      <li><strong>Complete Professional Bundles:</strong> Includes felt mallets, leather wands, and silk brocade cushions.</li>
    </ul>

    <p>Please find attached our <strong>Studio &amp; Wellness Catalog PDF</strong> with audio sound specs and direct studio pricing.</p>

    <p>May we send you high-definition acoustic audio samples or discuss a customized bowl set for your space?</p>

    <div class="footer">
      <p>In harmony,<br>
      <strong>{p['sender_name']}</strong><br>
      Artisan Sound Healing Specialist | {p['sender_company']}<br>
      {p['sender_contact']}</p>
    </div>
  </div>
</body>
</html>
"""
    return {"subject": subject, "body_text": body_text, "body_html": body_html}


# ==============================================================================
# TIER 3 TEMPLATES (SOLO PRACTITIONERS & BOUTIQUES)
# ==============================================================================
def render_tier3_content(p: Dict[str, str]) -> Dict[str, str]:
    """Render Tier 3 practitioner and boutique retail outreach copy."""
    subject = f"Handcrafted Himalayan Singing Bowls for {p['salutation']}"

    body_text = f"""Dear {p['salutation']},

Greetings from {p['sender_company']}.

We handcraft genuine Himalayan singing bowls in Nepal using ancestral hammer-forging techniques.

Whether you are looking to enrich your personal meditation space or discover handcrafted acoustic instruments:
-> Recommended Selection: {p['outreach_angle']}
-> Authentic 7-Metals Formulation with traditional mantras engraved by master artisans
-> Each bowl individually tested and tuned for deep soothing vibrations

Please find attached our artisan catalog presentation PDF detailing our handcrafted bowls, meditation bells, and brocade accessories.

We would be delighted to assist you in selecting the ideal bowl.

Warmest regards,

{p['sender_name']}
{p['sender_company']}
{p['sender_contact']}
"""

    body_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #222; }}
    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
    .header {{ border-bottom: 2px solid #F59E0B; padding-bottom: 12px; margin-bottom: 20px; }}
    .title {{ font-size: 20px; color: #78350f; font-weight: 700; margin: 0; }}
    .badge {{ display: inline-block; background: #fef3c7; color: #b45309; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; margin-top: 6px; }}
    .highlight-box {{ background: #fffbeb; border-left: 4px solid #F59E0B; padding: 14px 18px; margin: 18px 0; border-radius: 4px; }}
    .footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h2 class="title">Himalayan Artisan Singing Bowls</h2>
      <span class="badge">Artisan Handcrafted Collection</span>
    </div>
    <p>Dear <strong>{p['salutation']}</strong>,</p>
    <p>We handcraft genuine Himalayan singing bowls in Nepal using ancestral hammer-forging techniques.</p>
    
    <div class="highlight-box">
      <strong>Curated Artisan Selection:</strong><br>
      {p['outreach_angle']}
    </div>

    <p>Every bowl is individually hammered from 7 sacred metals and tested to produce deeply grounding overtones.</p>
    <p>Attached is our <strong>Artisan Catalog Presentation PDF</strong> showcasing our bowl collections and handmade accessories.</p>

    <div class="footer">
      <p>Warmest regards,<br>
      <strong>{p['sender_name']}</strong><br>
      {p['sender_company']}<br>
      {p['sender_contact']}</p>
    </div>
  </div>
</body>
</html>
"""
    return {"subject": subject, "body_text": body_text, "body_html": body_html}


# ==============================================================================
# UNIFIED RENDER FUNCTION
# ==============================================================================
def render_email_draft(
    buyer: Dict[str, str],
    tier: Optional[str] = None,
    attachment_path: Optional[Path] = None,
) -> EmailDraft:
    """Compose a complete, personalized EmailDraft for a buyer lead.

    Args:
        buyer: Normalized buyer dictionary with email, name, company, etc.
        tier: Optional explicit tier override (defaults to buyer.get('tier')).
        attachment_path: Optional custom PDF attachment path.

    Returns:
        EmailDraft object.
    """
    to_email = (buyer.get("email") or "").strip().lower()
    to_name = (buyer.get("buyer_name") or "").strip()
    company_name = (buyer.get("company_name") or "").strip()
    target_tier = tier or buyer.get("tier", config.TIER_2)

    placeholders = get_personalized_placeholders(buyer)

    if config.TIER_1 in target_tier:
        content = render_tier1_content(placeholders)
    elif config.TIER_3 in target_tier:
        content = render_tier3_content(placeholders)
    else:
        content = render_tier2_content(placeholders)

    # Resolve PDF attachment
    final_attachment = attachment_path if attachment_path is not None else config.PRESENTATION_PATH
    if final_attachment and not Path(final_attachment).exists():
        final_attachment = None

    return EmailDraft(
        to_email=to_email,
        to_name=to_name,
        company_name=company_name,
        subject=content["subject"],
        body_text=content["body_text"],
        body_html=content["body_html"],
        attachment_path=final_attachment,
    )
