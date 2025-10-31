from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml
from fastapi import APIRouter
from pydantic import BaseModel, Field
from urllib.parse import urlparse, urljoin

from app.services.fetcher import fetch_html
from app.services.keyphrases import extract_keyphrases
from app.services.lighthouse import fetch_psi
from app.utils.url_validator import validate_url_or_raise, SSRFProtectionError
from app.core.self_url import get_self_base_url


router = APIRouter(prefix="/orchestrator", tags=["orchestrator"], include_in_schema=True)

# ============================
# Load scoring rules at module import
# ============================
_SCORING_RULES: Dict[str, Any] = {}

def _load_scoring_rules() -> Dict[str, Any]:
    """Load scoring rules from YAML file on first use."""
    global _SCORING_RULES
    if not _SCORING_RULES:
        rules_path = Path(__file__).parent.parent.parent.parent / "scoring_rules.yaml"
        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as f:
                _SCORING_RULES = yaml.safe_load(f) or {}
        else:
            # Fallback to empty rules if file not found
            _SCORING_RULES = {"aeo_dimensions": [], "geo_dimensions": [], "weaknesses": []}
    return _SCORING_RULES


# ============================
# Input / Output Schemas
# ============================

class FeaturesInput(BaseModel):
    use_lighthouse: bool = True
    use_keybert: bool = True
    use_schema_parser: bool = True
    use_gbp_lookup: bool = True
    use_map_geocode: bool = True
    use_competitors_probe: bool = True


class OrchestratorInput(BaseModel):
    url: str
    free_test_mode: bool = False
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    geo_bias: Optional[str] = None
    frontend_base_url: str = "http://localhost:5174"
    backend_base_url: str = "http://localhost:8001"
    features: FeaturesInput = Field(default_factory=FeaturesInput)


# Output schema models (structured to match required shape)

class HealthService(BaseModel):
    name: str
    ok: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class HealthOutput(BaseModel):
    all_services_ok: bool
    services: List[HealthService]
    errors: List[str] = Field(default_factory=list)


class TargetOutput(BaseModel):
    input_url: str
    final_url: str
    http_status: Optional[int]
    canonical: Optional[str]


class BusinessGBP(BaseModel):
    matched: bool
    place_id: Optional[str]
    short_summary: Optional[str]


class BusinessGeo(BaseModel):
    lat: Optional[float]
    lng: Optional[float]


class BusinessOutput(BaseModel):
    name: Optional[str]
    dba: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    street_address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    hours: Optional[str]
    categories: List[str]
    service_areas: List[str]
    geo: BusinessGeo
    gbp: BusinessGBP
    # Local SEO boolean flags
    nap_detected: bool = False
    localbusiness_schema_detected: bool = False
    organization_schema_detected: bool = False
    google_business_hint: bool = False
    apple_business_connect_hint: bool = False


class ContentHeadings(BaseModel):
    h1: List[str]
    h2: List[str]
    h3: List[str]


class ContentOutput(BaseModel):
    title: Optional[str]
    meta_description: Optional[str]
    headings: ContentHeadings
    schema_types: List[str]
    structured_data_summary: Optional["StructuredDataSummary"] = None
    faq_count: int
    internal_links: int
    external_links: int


class ScoreDimension(BaseModel):
    name: str
    score: int
    rationale: str
    evidence: List[str]


class ScoresAEO(BaseModel):
    total: int
    dimensions: List[ScoreDimension]


class ScoresGEO(BaseModel):
    total: int
    dimensions: List[ScoreDimension]


class ScoresPSI(BaseModel):
    performance: Optional[int]
    seo: Optional[int]
    accessibility: Optional[int]
    best_practices: Optional[int]
    top_opportunities: List[Dict[str, str]]


class ScoresOutput(BaseModel):
    aeo: ScoresAEO
    geo: ScoresGEO
    psi: ScoresPSI


class PhraseItem(BaseModel):
    phrase: str
    weight: float
    intent: str


class WeaknessItem(BaseModel):
    title: str
    impact: str
    evidence: List[str]
    fix_summary: str


class CompetitorItem(BaseModel):
    name: str
    url: str


class DashPreview(BaseModel):
    business_header: bool
    map_pin: bool
    components: List[str]


class DashPremium(BaseModel):
    enabled: bool
    components: List[str]


class DashboardsOutput(BaseModel):
    preview: DashPreview
    premium: DashPremium


class CheckoutOutput(BaseModel):
    status: str
    stripe_checkout_url: Optional[str]
    premium_access: bool


class TelemetryOutput(BaseModel):
    elapsed_ms: int
    notes: List[str]


class OrchestratorOutput(BaseModel):
    status: str
    health: HealthOutput
    target: TargetOutput
    business: BusinessOutput
    content: ContentOutput
    scores: ScoresOutput
    keyphrases: List[PhraseItem]
    weaknesses: List[WeaknessItem]
    competitors: List[CompetitorItem]
    dashboards: DashboardsOutput
    checkout: CheckoutOutput
    telemetry: TelemetryOutput


# New compact summary for structured data counts/types
class StructuredDataSummary(BaseModel):
    json_ld_count: int = 0
    microdata_count: int = 0
    opengraph_count: int = 0
    types: List[str] = Field(default_factory=list)


# ============================
# Helpers
# ============================


def _resolve_final_url(url: str, timeout: int = 10) -> tuple[str, Optional[int]]:
    """Follow redirects to get final URL and a status code with minimal overhead."""
    try:
        import httpx
        with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}) as client:
            r = client.get(url)
            return str(r.url), r.status_code
    except Exception:
        return url, None


def _get_canonical(soup) -> Optional[str]:
    try:
        link = soup.find("link", rel=lambda v: v and "canonical" in v.lower())
        href = link.get("href") if link else None
        return href.strip() if href else None
    except Exception:
        return None


def _parse_html_basic(html: str, base: str) -> dict:
    from bs4 import BeautifulSoup
    # Prefer robust title extraction with multiple fallbacks
    from app.services.fetcher import extract_title as robust_extract_title
    soup = BeautifulSoup(html or "", "html.parser")
    # Title via robust extractor: <title> -> og:title -> twitter:title -> <h1> -> hostname
    title = robust_extract_title(html or "", url=base)
    meta_desc = None
    md_tag = soup.find("meta", attrs={"name": "description"})
    if md_tag and md_tag.get("content"):
        meta_desc = md_tag.get("content").strip()
    # OG description fallback
    if not meta_desc:
        ogd = soup.find("meta", property="og:description")
        if ogd and ogd.get("content"):
            meta_desc = ogd.get("content").strip()

    # Headings
    def texts(tags):
        return [t.get_text(strip=True) for t in soup.find_all(tags) if t.get_text(strip=True)]

    h1 = texts("h1")
    h2 = texts("h2")
    h3 = texts("h3")

    # Links
    parsed_host = urlparse(base).hostname or ""
    internal = 0
    external = 0
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        if not href or href.startswith("#"):
            continue
        full = urljoin(base, href)
        h = urlparse(full).hostname or ""
        if h and h == parsed_host:
            internal += 1
        elif h:
            external += 1

    # Canonical
    canonical = _get_canonical(soup)

    return {
        "title": title,
        "meta_description": meta_desc,
        "headings": {"h1": h1, "h2": h2, "h3": h3},
        "internal_links": internal,
        "external_links": external,
        "canonical": canonical,
    }


def _extract_structured_data_summary(html: str, base_url: str) -> tuple[StructuredDataSummary, int, dict]:
    """Fast, safe structured-data extraction.

    - Never raises; on error, returns empty summary.
    - Counts json-ld/microdata/opengraph blocks.
    - Collects detected @type values (normalized) from JSON-LD and Microdata.
    - Also derives faq_count by detecting FAQPage in JSON-LD.
    """
    summary = StructuredDataSummary()
    faq_count = 0
    raw: dict = {}

    # Local helpers
    def _as_list(x: Any) -> List[Any]:
        return x if isinstance(x, list) else ([] if x is None else [x]) if isinstance(x, (dict, str)) else []

    def _norm_type_name(val: Any) -> List[str]:
        out: List[str] = []
        if val is None:
            return out
        if isinstance(val, list):
            for v in val:
                out.extend(_norm_type_name(v))
            return out
        s = str(val)
        if not s:
            return out
        # Take the last path segment for IRIs
        out.append(s.split("/")[-1])
        return out

    try:
        import extruct
        from w3lib.html import get_base_url  # type: ignore
        base = get_base_url(html, base_url) if html else base_url
        data = extruct.extract(html or "", base_url=base, syntaxes=["json-ld", "microdata", "opengraph"]) or {}
        raw = data if isinstance(data, dict) else {}

        jsonld_list = raw.get("json-ld") if isinstance(raw, dict) else None
        micro_list = raw.get("microdata") if isinstance(raw, dict) else None
        og_list = raw.get("opengraph") if isinstance(raw, dict) else None

        jl = jsonld_list if isinstance(jsonld_list, list) else []
        md = micro_list if isinstance(micro_list, list) else []
        og = og_list if isinstance(og_list, list) else []

        summary.json_ld_count = len(jl)
        summary.microdata_count = len(md)
        summary.opengraph_count = len(og)

        types: List[str] = []

        # JSON-LD types and FAQ detection
        for item in jl:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            t_norm = _norm_type_name(t)
            if any(str(x).lower() == "faqpage" for x in _as_list(t)):
                faq_count += 1
            types.extend(t_norm)

        # Microdata types
        for md_item in md:
            if not isinstance(md_item, dict):
                continue
            t = md_item.get("type")
            types.extend(_norm_type_name(t))

        # De-duplicate, preserve order
        seen = set()
        uniq: List[str] = []
        for t in types:
            key = t.strip()
            if not key:
                continue
            key_lower = key.lower()
            if key_lower in seen:
                continue
            seen.add(key_lower)
            uniq.append(key)
        summary.types = uniq
    except Exception:
        # On any failure, return empty but safe summary
        pass

    return summary, faq_count, raw


def _extract_business_entity(schema_data: dict, html_text: str, html_lower: str, out_links: List[str]) -> dict:
    """Extract comprehensive business NAP and local SEO signals."""
    name = None
    dba = None
    phone = None
    email = None
    address = None
    street_address = None
    city = None
    state = None
    postal_code = None
    hours = None
    categories: List[str] = []
    service_areas: List[str] = []
    
    # Boolean flags for local SEO signals
    localbusiness_schema_detected = False
    organization_schema_detected = False
    has_address_in_schema = False

    # JSON-LD first
    try:
        for item in schema_data.get("json-ld", []) or []:
            t = item.get("@type")
            t_list = t if isinstance(t, list) else [t]
            
            # Check for LocalBusiness or Organization schema
            for schema_type in t_list:
                if schema_type:
                    schema_type_lower = str(schema_type).lower()
                    if schema_type_lower == "localbusiness" or "localbusiness" in schema_type_lower:
                        localbusiness_schema_detected = True
                    if schema_type_lower == "organization":
                        organization_schema_detected = True
            
            if any(str(x).lower() in ("organization", "localbusiness") for x in t_list if x):
                name = name or item.get("name")
                dba = dba or item.get("alternateName")
                # Phone
                phone = phone or item.get("telephone")
                # Email
                email = email or item.get("email")
                # Address - extract both full and individual components
                addr = item.get("address") or {}
                if isinstance(addr, dict):
                    street_address = street_address or addr.get("streetAddress")
                    city = city or addr.get("addressLocality")
                    state = state or addr.get("addressRegion")
                    postal_code = postal_code or addr.get("postalCode")
                    
                    parts = [street_address, city, state, postal_code, addr.get("addressCountry")]
                    address = address or ", ".join([p for p in parts if p]) or None
                    
                    if any([street_address, city, state, postal_code]):
                        has_address_in_schema = True
                        
                # Opening hours
                oh = item.get("openingHours") or item.get("openingHoursSpecification")
                if isinstance(oh, list):
                    hours = hours or "; ".join([json.dumps(x) if isinstance(x, dict) else str(x) for x in oh])
                elif isinstance(oh, (str, dict)):
                    hours = hours or (json.dumps(oh) if isinstance(oh, dict) else oh)
                # Category
                tp = item.get("@type")
                if isinstance(tp, list):
                    categories.extend([str(x) for x in tp])
                elif tp:
                    categories.append(str(tp))
                # Service area
                sa = item.get("areaServed")
                if isinstance(sa, list):
                    service_areas.extend([str(x) for x in sa])
                elif isinstance(sa, str):
                    service_areas.append(sa)
    except Exception:
        pass

    # Fallback regex from HTML text for phone and email
    try:
        if not phone:
            m = re.search(r"(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", html_text)
            phone = m.group(0) if m else None
        if not email:
            m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", html_text)
            email = m.group(0) if m else None
    except Exception:
        pass
    
    # Fallback regex for US address components if not in schema
    try:
        if not city:
            # Look for city, state zip pattern (e.g., "San Francisco, CA 94102")
            city_pattern = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', html_text)
            if city_pattern:
                city = city or city_pattern.group(1)
                state = state or city_pattern.group(2)
                postal_code = postal_code or city_pattern.group(3)
        
        if not postal_code:
            # Look for 5-digit or 9-digit zip code
            zip_match = re.search(r'\b\d{5}(?:-\d{4})?\b', html_text)
            if zip_match:
                postal_code = postal_code or zip_match.group(0)
        
        if not state and not city:
            # Look for state abbreviation
            state_match = re.search(r'\b([A-Z]{2})\s+\d{5}', html_text)
            if state_match:
                state = state or state_match.group(1)
    except Exception:
        pass

    # Detect Google Business and Apple Business Connect hints from links
    google_business_hint = False
    apple_business_connect_hint = False
    
    try:
        all_links = " ".join(out_links + [html_lower])
        if "google.com/maps" in all_links or "maps.google.com" in all_links or "g.page" in all_links or "business.google.com" in all_links:
            google_business_hint = True
        if "maps.apple.com" in all_links or "businessconnect.apple.com" in all_links:
            apple_business_connect_hint = True
    except Exception:
        pass

    # Determine if NAP (Name, Address, Phone) is detected
    nap_detected = bool(name and phone and (address or (city and state)))

    # Normalize categories
    categories = list({c.split("/")[-1] for c in categories if c})

    return {
        "name": name,
        "dba": dba,
        "phone": phone,
        "email": email,
        "address": address,
        "street_address": street_address,
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "hours": hours,
        "categories": categories,
        "service_areas": service_areas,
        "nap_detected": nap_detected,
        "localbusiness_schema_detected": localbusiness_schema_detected,
        "organization_schema_detected": organization_schema_detected,
        "google_business_hint": google_business_hint,
        "apple_business_connect_hint": apple_business_connect_hint,
    }


def _get_nested_value(data: dict, field: str) -> Any:
    """Get nested field value from dict using dot notation (e.g., 'business.name')."""
    keys = field.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def _apply_rule(rule: dict, data: dict, rules_config: dict) -> tuple[int, List[str]]:
    """Apply a single scoring rule and return points + evidence."""
    rule_type = rule.get("type", "")
    field = rule.get("field", "")
    value = _get_nested_value(data, field)
    evidence = []
    points = 0

    # Handle different rule types
    if rule_type == "faq_count":
        faq_count = value or 0
        points = faq_count * rule.get("multiplier", 1)
        evidence.append(f"faq_count={faq_count}")

    elif rule_type == "question_headings":
        h2_list = value or []
        patterns = rules_config.get("question_patterns", [])
        q_heads = [h for h in h2_list if "?" in h or h.lower().startswith(tuple(patterns))]
        points = len(q_heads) * rule.get("multiplier", 1)
        evidence.append(f"q_heads={len(q_heads)}")

    elif rule_type == "schema_diversity":
        schema_types = value or []
        unique_count = len(set(schema_types))
        contrib = min(rule.get("max_contribution", 70), unique_count * rule.get("multiplier", 1))
        points = contrib
        evidence.extend(schema_types[:5])

    elif rule_type == "local_business_bonus":
        schema_types = value or []
        if any(s.lower() == "localbusiness" for s in schema_types):
            points = rule.get("bonus", 0)
            evidence.append("LocalBusiness present")

    elif rule_type in ("business_name", "business_phone", "business_address"):
        if value:
            points = rule.get("points", 0)
            evidence.append(f"{field}=present")

    elif rule_type == "internal_links":
        internal_links = value or 0
        formula = rule.get("formula", "")
        if "min(50, value // 10)" in formula:
            points = min(50, internal_links // 10)
        evidence.append(f"internal_links={internal_links}")

    elif rule_type == "text_length":
        text_len = value or 0
        formula = rule.get("formula", "")
        if "min(70, value // 800)" in formula:
            points = min(70, text_len // 800)
        evidence.append(f"text_len={text_len}")

    elif rule_type == "about_link":
        links_text = " ".join(value or []).lower()
        if "about" in links_text:
            points = rule.get("points", 0)
            evidence.append("About link detected")

    elif rule_type == "review_content":
        html_lower = value or ""
        if "review" in html_lower:
            points = rule.get("points", 0)
            evidence.append("Review content detected")

    elif rule_type == "citation_sources":
        out_links_text = " ".join(value or [])
        targets = rule.get("targets", [])
        cites = sum(1 for t in targets if t in out_links_text)
        points = cites * rule.get("multiplier", 1)
        evidence.append(f"matches={cites}")

    elif rule_type == "address_present":
        if value:
            points = rule.get("points", 0)
            evidence.append(f"address=present")

    elif rule_type == "map_embed":
        html_lower = value or ""
        if "maps.google" in html_lower:
            points = rule.get("points", 0)
            evidence.append("Google Maps embed detected")

    elif rule_type == "service_areas":
        if value:
            points = rule.get("points", 0)
            evidence.append(f"areas={len(value) if isinstance(value, list) else 1}")

    elif rule_type == "location_schema_types":
        schema_types = value or []
        targets = rule.get("targets", [])
        if any(s.lower() in targets for s in schema_types):
            points = rule.get("points", 0)
            evidence.append("Location schema present")

    elif rule_type in ("phone_clickable", "email_clickable"):
        if value:
            points = rule.get("points", 0)
            evidence.append(f"{field}=present")

    elif rule_type == "review_mentions":
        html_lower = value or ""
        if "review" in html_lower:
            points = rule.get("points", 0)
            evidence.append("Review mentions detected")

    elif rule_type == "psi_performance":
        perf = value
        if perf is not None:
            formula = rule.get("formula", "")
            if "value // 2" in formula:
                points = perf // 2
        else:
            points = rule.get("fallback_score", 0) - rule.get("base_score", 0)
        evidence.append(f"performance={perf}")

    return points, evidence


def _compute_scores(page: dict, biz: dict, psi: dict) -> tuple[ScoresAEO, ScoresGEO, List[WeaknessItem]]:
    """Compute AEO and GEO scores based on external rules file."""
    rules_config = _load_scoring_rules()
    
    # Prepare unified data dict for rule evaluation
    data = {
        "faq_count": page.get("faq_count", 0),
        "headings": page.get("headings", {}),
        "schema_types": page.get("schema_types", []),
        "business": biz,
        "internal_links": page.get("internal_links", 0),
        "text_len": page.get("text_len", 0),
        "links_text": page.get("links_text", []),
        "html_lower": page.get("html_lower", ""),
        "out_links": page.get("out_links", []),
        "psi": psi,
    }

    # AEO dimensions
    dims_aeo: List[ScoreDimension] = []
    for dim_config in rules_config.get("aeo_dimensions", []):
        score = dim_config.get("base_score", 0)
        all_evidence = []
        
        for rule in dim_config.get("rules", []):
            rule_points, rule_evidence = _apply_rule(rule, data, rules_config)
            score += rule_points
            all_evidence.extend(rule_evidence)
        
        score = min(dim_config.get("max_score", 100), score)
        dims_aeo.append(ScoreDimension(
            name=dim_config["name"],
            score=score,
            rationale=dim_config.get("rationale", ""),
            evidence=all_evidence
        ))
    
    total_aeo = int(round(sum(d.score for d in dims_aeo) / len(dims_aeo))) if dims_aeo else 0

    # GEO dimensions
    dims_geo: List[ScoreDimension] = []
    for dim_config in rules_config.get("geo_dimensions", []):
        score = dim_config.get("base_score", 0)
        all_evidence = []
        
        for rule in dim_config.get("rules", []):
            rule_points, rule_evidence = _apply_rule(rule, data, rules_config)
            score += rule_points
            all_evidence.extend(rule_evidence)
        
        score = min(dim_config.get("max_score", 100), score)
        dims_geo.append(ScoreDimension(
            name=dim_config["name"],
            score=score,
            rationale=dim_config.get("rationale", ""),
            evidence=all_evidence
        ))
    
    total_geo = int(round(sum(d.score for d in dims_geo) / len(dims_geo))) if dims_geo else 0

    # Weaknesses
    weaknesses: List[WeaknessItem] = []
    for weak_config in rules_config.get("weaknesses", []):
        condition = weak_config.get("condition", {})
        field = condition.get("field", "")
        operator = condition.get("operator", "")
        expected_value = condition.get("value")
        
        field_value = _get_nested_value(data, field)
        triggered = False
        
        if operator == "not_present":
            triggered = not field_value
        elif operator == "not_contains":
            if isinstance(field_value, list):
                triggered = not any(str(v).lower() == str(expected_value).lower() for v in field_value)
            else:
                triggered = False
        elif operator == "less_than":
            triggered = (field_value or 0) < expected_value
        elif operator == "equals":
            triggered = field_value == expected_value
        
        if triggered:
            evidence = weak_config.get("evidence", [])
            evidence_template = weak_config.get("evidence_template", "")
            if evidence_template:
                # Simple template substitution
                evidence = [evidence_template.format(**{k: _get_nested_value(data, k) for k in ["psi.performance", "internal_links", "text_len"]})]
            
            weaknesses.append(WeaknessItem(
                title=weak_config["title"],
                impact=weak_config.get("impact", "med"),
                evidence=evidence,
                fix_summary=weak_config.get("fix_summary", "")
            ))

    return (
        ScoresAEO(total=total_aeo, dimensions=dims_aeo),
        ScoresGEO(total=total_geo, dimensions=dims_geo),
        weaknesses,
    )


# ============================
# Route
# ============================


@router.post("/run", response_model=OrchestratorOutput)
def run_orchestration(payload: OrchestratorInput) -> OrchestratorOutput:
    start = time.time()
    notes: List[str] = []

    # Health checks
    services: List[HealthService] = []
    errors: List[str] = []
    all_ok = True

    # 1) backend health
    ok = False
    bh_details: Dict[str, Any] = {}
    internal_url = f"{get_self_base_url()}/api/v1/utils/health-check/"
    external_url = f"{payload.backend_base_url}/api/v1/utils/health-check/" if payload.backend_base_url else None
    # Try internal (8000) first
    try:
        r = requests.get(internal_url, timeout=5)
        if r.status_code == 200:
            ok = True
            bh_details = {"status": 200, "url": internal_url}
    except Exception as e:
        notes.append(f"backend_health_internal_error: {e}")
    # Fallback to external (8001) if needed
    if not ok and external_url:
        try:
            r2 = requests.get(external_url, timeout=5)
            if r2.status_code == 200:
                ok = True
                bh_details = {"status": 200, "url": external_url}
        except Exception as e:
            notes.append(f"backend_health_external_error: {e}")
    services.append(HealthService(name="backend_health", ok=ok, details=bh_details)) ; all_ok = all_ok and ok

    # 2) PSI
    psi_ok = True
    psi_details: Dict[str, Any] = {"perf": None}
    if payload.features.use_lighthouse:
        try:
            psi_test = fetch_psi("https://example.com/")
            psi_ok = bool(psi_test.get("available"))
            psi_details["perf"] = psi_test.get("performance")
            if not psi_ok:
                notes.append("psi_unavailable")
        except Exception as e:
            psi_ok = False
            notes.append(f"psi_error: {e}")
    services.append(HealthService(name="psi", ok=psi_ok, details=psi_details)); all_ok = all_ok and psi_ok

    # 3) KeyBERT
    kb_ok = True
    try:
        sample = "Local injury lawyer near Irving TX free consultation personal injury law firm"
        phrases = extract_keyphrases(sample, top_n=8, timeout_ms=1500, cache_key="healthcheck")
        kb_ok = len(phrases) >= 3
        if not kb_ok:
            notes.append("keybert_few_phrases")
    except Exception as e:
        kb_ok = False
        notes.append(f"keybert_error: {e}")
    services.append(HealthService(name="keybert", ok=kb_ok, details={})) ; all_ok = all_ok and kb_ok

    # 4) Schema parser (we'll validate later after fetch)
    schema_parser_ok = True
    services.append(HealthService(name="schema_parser", ok=schema_parser_ok, details={})) ; all_ok = all_ok and schema_parser_ok

    # 5) SSRF guard
    ssrf_ok = True
    try:
        try:
            validate_url_or_raise("http://127.0.0.1")
            ssrf_ok = False  # should have raised
        except SSRFProtectionError:
            ssrf_ok = True
    except Exception as e:
        ssrf_ok = False
        notes.append(f"ssrf_check_error: {e}")
    services.append(HealthService(name="ssrf_guard", ok=ssrf_ok, details={})) ; all_ok = all_ok and ssrf_ok

    # 6) Optional GBP lookup / geocoder
    services.append(HealthService(name="gbp_lookup", ok=False, details={})) ; all_ok = False if payload.features.use_gbp_lookup else all_ok
    services.append(HealthService(name="geocoder", ok=False, details={})) ; all_ok = False if payload.features.use_map_geocode else all_ok

    # Fetch & normalize
    try:
        validate_url_or_raise(payload.url)
    except SSRFProtectionError as e:
        errors.append(str(e))
    final_url, status_code = _resolve_final_url(payload.url)

    # async fetch_html via anyio
    html: str = ""
    html_ms = 0
    try:
        import anyio
        timeout_s = int(os.getenv("EXTRACT_TIMEOUT_SECONDS", "20"))
        html, html_ms = anyio.run(fetch_html, final_url, timeout_s)
    except Exception as e:
        notes.append(f"html_fetch_error: {e}")

    # Parse HTML
    basic = _parse_html_basic(html, final_url)
    canonical = basic.get("canonical")

    # Structured data summary (safe & compact)
    sd_summary, faq_count, schema_raw = _extract_structured_data_summary(html, final_url)
    basic["schema_types"] = sd_summary.types
    basic["faq_count"] = faq_count

    # Text length
    text_len = 0
    html_lower = (html or "").lower()
    try:
        import trafilatura
        text = trafilatura.extract(html, output_format="txt", include_comments=False) or ""
        text_len = len(text)
    except Exception:
        text = ""
    basic["text_len"] = text_len
    basic["html_lower"] = html_lower

    # Collect visible link texts for E-E-A-T heuristic
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    links_text = [a.get_text(strip=True) for a in soup.find_all("a") if a.get_text(strip=True)]
    out_links = [a.get("href") or "" for a in soup.find_all("a")]
    basic["links_text"] = links_text
    basic["out_links"] = out_links

    # Business entity with local SEO signals
    biz_data = _extract_business_entity(schema_raw, html, html_lower, out_links)

    # 5) CrewAI / LLM availability (optional)
    from app.core.config import settings as _settings
    try:
        import os as _os
        from app.services.llm_factory import _resolve_base_url as _llm_resolve
        crew_enabled = bool(_settings.CREW_AI_ENABLED)
        base_url = _llm_resolve(_os.getenv("OLLAMA_HOST"))
        ok_ai = False
        details_ai: dict = {"enabled": crew_enabled, "base_url": base_url}
        if crew_enabled:
            try:
                with httpx.Client(timeout=2.0) as client:
                    # Ollama health probe: list tags/models
                    r = client.get(f"{base_url}/api/tags")
                    details_ai["status_code"] = r.status_code
                    if r.status_code == 200:
                        ok_ai = True
            except Exception as e:
                details_ai["error"] = str(e)
        # If disabled, report but do not fail overall health
        services.append(HealthService(name="crewai", ok=ok_ai if crew_enabled else False, details=details_ai))
        all_ok = (all_ok and ok_ai) if crew_enabled else all_ok
    except Exception as e:
        services.append(HealthService(name="crewai", ok=False, details={"error": f"probe_failed: {e}"}))
        all_ok = all_ok

    # GBP & Geocode stubs
    gbp = {"matched": False, "place_id": None, "short_summary": None}
    geo = {"lat": None, "lng": None}

    # PSI on target
    psi_block = {"performance": None, "seo": None, "accessibility": None, "best_practices": None, "top_opportunities": []}
    psi = {}
    if payload.features.use_lighthouse:
        try:
            psi = fetch_psi(final_url)
            psi_block["performance"] = psi.get("performance")
            psi_block["seo"] = psi.get("seo")
            # Accessibility & Best Practices not returned by our helper yet
            psi_block["accessibility"] = None
            psi_block["best_practices"] = None
        except Exception as e:
            notes.append(f"psi_fetch_error: {e}")

    # Keyphrases
    phrases: List[PhraseItem] = []
    if payload.features.use_keybert and text:
        try:
            kp = extract_keyphrases(text, top_n=8, timeout_ms=int(os.getenv("KEYPHRASES_TIMEOUT_MS", "2000")), cache_key=final_url)
            for i, p in enumerate(kp):
                phrases.append(PhraseItem(phrase=p, weight=max(0.1, 1.0 - i * 0.05), intent=("Local" if " tx" in text.lower() or " texas" in text.lower() else "Informational")))
        except Exception as e:
            notes.append(f"keyphrases_error: {e}")

    # Scores & weaknesses
    aeo, geo_scores, weaknesses = _compute_scores({
        **basic,
        "faq_count": faq_count,
    }, {
        **biz_data,
        "geo": geo,
    }, psi)

    # Competitors (stub)
    competitors: List[CompetitorItem] = []
    if payload.features.use_competitors_probe and biz_data.get("name"):
        # In local dev, skip live search; return empty
        competitors = []

    # Checkout gating
    if payload.free_test_mode:
        checkout = CheckoutOutput(status="skipped_free_test", stripe_checkout_url=None, premium_access=False)
    else:
        # Stripe integration not wired here; degrade gracefully
        checkout = CheckoutOutput(status="error", stripe_checkout_url=None, premium_access=False)
        notes.append("stripe_not_configured")

    # Health assemble
    health = HealthOutput(
        all_services_ok=all_ok,
        services=services,
        errors=errors,
    )

    # Final output build
    elapsed_ms = int((time.time() - start) * 1000)
    status = "ok" if not errors else ("degraded" if not all_ok else "ok")

    return OrchestratorOutput(
        status=status if all_ok else "degraded",
        health=health,
        target=TargetOutput(input_url=payload.url, final_url=final_url, http_status=status_code, canonical=canonical),
        business=BusinessOutput(
            name=biz_data.get("name"),
            dba=biz_data.get("dba"),
            phone=biz_data.get("phone"),
            email=biz_data.get("email"),
            address=biz_data.get("address"),
            street_address=biz_data.get("street_address"),
            city=biz_data.get("city"),
            state=biz_data.get("state"),
            postal_code=biz_data.get("postal_code"),
            hours=biz_data.get("hours"),
            categories=biz_data.get("categories") or [],
            service_areas=biz_data.get("service_areas") or [],
            geo=BusinessGeo(**geo),
            gbp=BusinessGBP(**gbp),
            nap_detected=biz_data.get("nap_detected", False),
            localbusiness_schema_detected=biz_data.get("localbusiness_schema_detected", False),
            organization_schema_detected=biz_data.get("organization_schema_detected", False),
            google_business_hint=biz_data.get("google_business_hint", False),
            apple_business_connect_hint=biz_data.get("apple_business_connect_hint", False),
        ),
        content=ContentOutput(
            title=basic.get("title"),
            meta_description=basic.get("meta_description"),
            headings=ContentHeadings(**basic.get("headings", {"h1": [], "h2": [], "h3": []})),
            schema_types=basic.get("schema_types", []),
            structured_data_summary=sd_summary,
            faq_count=basic.get("faq_count", 0),
            internal_links=basic.get("internal_links", 0),
            external_links=basic.get("external_links", 0),
        ),
        scores=ScoresOutput(
            aeo=aeo,
            geo=geo_scores,
            psi=ScoresPSI(**psi_block),
        ),
        keyphrases=phrases,
        weaknesses=weaknesses,
        competitors=competitors,
        dashboards=DashboardsOutput(
            preview=DashPreview(business_header=True, map_pin=True, components=["scores_dials", "psi_snapshot", "weakness_list", "benefit_blurb", "cta"]),
            premium=DashPremium(enabled=False, components=["deep_tasks", "competitor_table", "citation_audit", "history_trends", "report_export"]),
        ),
        checkout=checkout,
        telemetry=TelemetryOutput(elapsed_ms=elapsed_ms, notes=notes),
    )
