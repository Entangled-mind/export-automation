"""Dynamic query generator for generic product-to-buyer discovery.

Builds relevant commercial search strings for any user-entered product category
without hardcoding product-specific logic.
"""

from typing import List, Optional


BUYER_INTENT_TERMS = [
    "importer",
    "distributor",
    "wholesaler",
    "retailer",
    "buyer",
    "supplier",
    "dealer",
    "exporter",
    "sourcing company",
    "trading company",
    "manufacturer",
    '"contact"',
]


def clean_query_term(term: Optional[str]) -> str:
    """Normalize and strip quotes, extraneous whitespace, and non-printable chars from a term."""
    if not term:
        return ""
    cleaned = term.strip().strip('"\'')
    return " ".join(cleaned.split())


def generate_buyer_queries(
    product: str,
    country: Optional[str] = None,
    region: Optional[str] = None,
    buyer_type: Optional[str] = None,
    additional_context: Optional[str] = None,
    include_extended: bool = False,
) -> List[str]:
    """Generate dynamic buyer-intent queries for any product category.

    The search strategy adapts from product, country, region, buyer type, and search context.
    """
    clean_product = clean_query_term(product)
    if not clean_product:
        return []

    clean_country = clean_query_term(country) if country else ""
    clean_region = clean_query_term(region) if region else ""
    clean_buyer_type = clean_query_term(buyer_type).lower() if buyer_type else ""
    clean_context = clean_query_term(additional_context) if additional_context else ""
    quoted_product = f'"{clean_product}"'

    geo_country = f' "{clean_country}"' if clean_country else ""
    geo_region = f' "{clean_region}"' if clean_region else ""
    geo_segment = f'{geo_region}{geo_country}'

    query_map: List[str] = []
    if clean_country:
        query_map.append(f'{quoted_product} wholesale{geo_country}')
        query_map.append(f'{quoted_product} "contact"{geo_country}')
        query_map.append(f'{quoted_product} sourcing company{geo_country}')
        query_map.append(f'{quoted_product} trading company{geo_country}')
        query_map.append(f'{quoted_product} supplier{geo_country}')
        query_map.append(f'{quoted_product} exports{geo_country}')
        query_map.append(f'{quoted_product} procurement{geo_country}')

    for term in BUYER_INTENT_TERMS:
        if clean_buyer_type and clean_buyer_type not in {"any", "all"} and term.lower() in {"importer", "distributor", "wholesaler", "retailer", "dealer", "manufacturer"}:
            exact_buyer = clean_buyer_type
            query_map.append(f'{quoted_product} {exact_buyer}{geo_country}')
        query_map.append(f'{quoted_product} {term}{geo_country}')
        if clean_region:
            query_map.append(f'{quoted_product} {term}{geo_region}')
        if geo_segment:
            query_map.append(f'{quoted_product} {term}{geo_segment}')

    if clean_country and include_extended:
        query_map.append(f'{quoted_product} wholesale{geo_country}')
        query_map.append(f'{quoted_product} sourcing company{geo_country}')
        query_map.append(f'{quoted_product} trading company{geo_country}')
        query_map.append(f'{quoted_product} supplier{geo_country}')
        query_map.append(f'{quoted_product} exports{geo_country}')
        query_map.append(f'{quoted_product} procurement{geo_country}')

    if clean_context:
        query_map.append(f'{quoted_product} {clean_context}{geo_country}')

    deduped: List[str] = []
    seen = set()
    for q in query_map:
        normalized = " ".join(q.split())
        if normalized.lower() not in seen:
            seen.add(normalized.lower())
            deduped.append(normalized)

    # Return the complete unique set of buyer-intent variants. An arbitrary cap
    # here drops valid searches like "exporter" and "buyer" when multiple
    # country/region combinations are added.
    return deduped
