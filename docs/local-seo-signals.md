# Local SEO Signal Detection - Implementation Guide

## Overview

The analyzer now detects comprehensive local SEO signals including:

- **NAP (Name, Address, Phone)** components with individual field extraction
- **Schema markup** detection (LocalBusiness, Organization with address)
- **Platform hints** (Google Business Profile, Apple Business Connect)
- **Boolean flags** for quick local SEO status checks

## Updated API Response Schema

### BusinessOutput Model

```python
class BusinessOutput(BaseModel):
    # Basic NAP fields
    name: Optional[str]
    dba: Optional[str]
    phone: Optional[str]
    email: Optional[str]

    # Address fields (granular)
    address: Optional[str]           # Full formatted address
    street_address: Optional[str]    # Street number + name
    city: Optional[str]               # City/locality
    state: Optional[str]              # State/region (2-letter code)
    postal_code: Optional[str]        # ZIP/postal code (5 or 9 digit)

    # Additional business data
    hours: Optional[str]
    categories: List[str]
    service_areas: List[str]
    geo: BusinessGeo
    gbp: BusinessGBP

    # Local SEO boolean flags (NEW)
    nap_detected: bool = False                      # Name + Phone + (Address OR City+State)
    localbusiness_schema_detected: bool = False     # Has LocalBusiness JSON-LD
    organization_schema_detected: bool = False      # Has Organization JSON-LD with address
    google_business_hint: bool = False              # Links to Google Maps/GBP
    apple_business_connect_hint: bool = False       # Links to Apple Maps/Business Connect
```

## Detection Logic

### 1. NAP Detection (`nap_detected`)

**Triggers when:** Business has name AND phone AND (full address OR city+state)

```python
nap_detected = bool(name and phone and (address or (city and state)))
```

**Sources:**

1. **JSON-LD schema** (primary): `Organization` or `LocalBusiness` with `name`, `telephone`, `address`
2. **Regex fallback** (secondary): Phone pattern `(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}`

### 2. Address Component Extraction

**Individual fields extracted:**

```python
street_address: str  # From schema: address.streetAddress
city: str           # From schema: address.addressLocality
state: str          # From schema: address.addressRegion (or regex: 2-letter before ZIP)
postal_code: str    # From schema: address.postalCode (or regex: \d{5}(-\d{4})?)
```

**Fallback regex patterns:**

- **City, State, ZIP**: `([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)`
- **ZIP only**: `\b\d{5}(?:-\d{4})?\b`
- **State before ZIP**: `\b([A-Z]{2})\s+\d{5}`

### 3. LocalBusiness Schema Detection

**Triggers when:** JSON-LD contains `@type: "LocalBusiness"` or any subtype

```python
localbusiness_schema_detected = any(
    "localbusiness" in str(schema_type).lower()
    for schema_type in json_ld["@type"]
)
```

**Detects all LocalBusiness subtypes:**

- `LocalBusiness` (generic)
- `Attorney`, `Dentist`, `Restaurant`, `Store`, etc.

### 4. Organization Schema Detection

**Triggers when:** JSON-LD contains `@type: "Organization"` with postal address

```python
organization_schema_detected = (
    "@type" == "Organization" and
    "address" in json_ld and
    any address component present
)
```

### 5. Google Business Profile Hint

**Triggers when:** Page links to Google Maps or GBP

**Detected patterns:**

- `google.com/maps`
- `maps.google.com`
- `g.page/` (Google Business short URL)
- `business.google.com`

```python
google_business_hint = any([
    "google.com/maps" in all_links,
    "maps.google.com" in all_links,
    "g.page" in all_links,
    "business.google.com" in all_links,
])
```

### 6. Apple Business Connect Hint

**Triggers when:** Page links to Apple Maps or Business Connect

**Detected patterns:**

- `maps.apple.com`
- `businessconnect.apple.com`

```python
apple_business_connect_hint = any([
    "maps.apple.com" in all_links,
    "businessconnect.apple.com" in all_links,
])
```

## Response Examples

### Example 1: Complete Local Business

**URL:** `https://example-law-firm.com`

```json
{
  "business": {
    "name": "Smith & Associates Law",
    "dba": null,
    "phone": "+1-555-123-4567",
    "email": "contact@smithlaw.com",
    "address": "123 Main Street, San Francisco, CA 94102",
    "street_address": "123 Main Street",
    "city": "San Francisco",
    "state": "CA",
    "postal_code": "94102",
    "hours": "Mon-Fri: 9am-5pm",
    "categories": ["Attorney", "LocalBusiness"],
    "service_areas": ["San Francisco", "Bay Area"],
    "nap_detected": true,
    "localbusiness_schema_detected": true,
    "organization_schema_detected": true,
    "google_business_hint": true,
    "apple_business_connect_hint": false
  }
}
```

**Analysis:**

- ✅ Complete NAP
- ✅ Granular address components
- ✅ Both LocalBusiness and Organization schemas
- ✅ Google Maps embed detected
- ❌ No Apple Maps link

### Example 2: Partial NAP (Name + Phone Only)

**URL:** `https://online-consultant.com`

```json
{
  "business": {
    "name": "Digital Marketing Pro",
    "phone": "555-987-6543",
    "address": null,
    "street_address": null,
    "city": null,
    "state": null,
    "postal_code": null,
    "nap_detected": false,
    "localbusiness_schema_detected": false,
    "organization_schema_detected": true,
    "google_business_hint": false,
    "apple_business_connect_hint": false
  }
}
```

**Analysis:**

- ❌ Incomplete NAP (missing address)
- ⚠️ Only Organization schema (no LocalBusiness)
- ❌ No local platform links

### Example 3: No Local Signals

**URL:** `https://generic-blog.com`

```json
{
  "business": {
    "name": null,
    "phone": null,
    "address": null,
    "street_address": null,
    "city": null,
    "state": null,
    "postal_code": null,
    "nap_detected": false,
    "localbusiness_schema_detected": false,
    "organization_schema_detected": false,
    "google_business_hint": false,
    "apple_business_connect_hint": false
  }
}
```

**Analysis:**

- ❌ No NAP
- ❌ No local schema
- ❌ Not a local business

## Integration Points

### 1. Orchestrator Endpoint (`/api/v1/orchestrator/run`)

**Returns:** Full BusinessOutput with all flags in `business` section

```bash
curl -X POST http://localhost:8001/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "features": {}}'
```

### 2. Scan Job Teaser (`/api/v1/scan-jobs/{id}/status`)

**Returns:** Abbreviated business data in `teaser.business`:

```json
{
  "teaser": {
    "title": "Example Business",
    "business": {
      "name": "Example Co",
      "phone": "555-1234",
      "city": "San Francisco",
      "state": "CA",
      "nap_detected": true,
      "localbusiness_schema_detected": true,
      "organization_schema_detected": true,
      "google_business_hint": true,
      "apple_business_connect_hint": false
    }
  }
}
```

### 3. Scan Job Full Results (`/api/v1/scan-jobs/{id}/full`)

**Returns:** Complete business data in `business` section:

```json
{
  "business": {
    "name": "Example Co",
    "phone": "555-1234",
    "address": "123 Main St, San Francisco, CA 94102",
    "street_address": "123 Main St",
    "city": "San Francisco",
    "state": "CA",
    "postal_code": "94102",
    "nap_detected": true,
    "localbusiness_schema_detected": true,
    "organization_schema_detected": true,
    "google_business_hint": true,
    "apple_business_connect_hint": false
  }
}
```

## Code Implementation

### Orchestrator: `_extract_business_entity()`

**Location:** `backend/app/api/routes/orchestrator.py`

**Signature:**

```python
def _extract_business_entity(
    schema_data: dict,      # Parsed JSON-LD/microdata
    html_text: str,         # Raw HTML text for regex fallback
    html_lower: str,        # Lowercased HTML for pattern matching
    out_links: List[str]    # All href values for platform detection
) -> dict
```

**Returns dict with:**

- All NAP fields (name, phone, address components)
- All boolean flags (nap_detected, schema flags, platform hints)

**Key logic:**

1. Parse JSON-LD for LocalBusiness/Organization
2. Extract address components from schema
3. Regex fallback for phone/email/zip
4. Check out_links for Google/Apple patterns
5. Set nap_detected flag
6. Return comprehensive dict

### Worker: `process_scan_job()`

**Location:** `backend/app/worker.py`

**Inline business extraction:**

```python
# Extract structured data
schema_raw = extruct.extract(html, base_url=url, syntaxes=["json-ld", "microdata"])

# Parse business data
business_data = {}
for item in schema_raw.get("json-ld", []):
    if item.get("@type") in ["Organization", "LocalBusiness"]:
        biz_name = item.get("name")
        biz_phone = item.get("telephone")
        addr = item.get("address", {})
        biz_street = addr.get("streetAddress")
        biz_city = addr.get("addressLocality")
        biz_state = addr.get("addressRegion")
        biz_postal = addr.get("postalCode")
        # ... (set flags)
```

**Persists to:**

- `job.teaser_json.business` (abbreviated)
- `job.full_json.business` (complete)

## Use Cases

### 1. Local SEO Audit Dashboard

Display quick local SEO health:

```typescript
function LocalSEOHealth({ business }) {
  return (
    <div>
      <Badge color={business.nap_detected ? "green" : "red"}>
        {business.nap_detected ? "✓ NAP Complete" : "✗ NAP Missing"}
      </Badge>
      <Badge
        color={business.localbusiness_schema_detected ? "green" : "yellow"}
      >
        {business.localbusiness_schema_detected
          ? "✓ LocalBusiness Schema"
          : "⚠ No Schema"}
      </Badge>
      <Badge color={business.google_business_hint ? "green" : "gray"}>
        {business.google_business_hint ? "✓ GBP Linked" : "○ No GBP Link"}
      </Badge>
    </div>
  );
}
```

### 2. NAP Consistency Checker

Verify NAP across multiple pages:

```python
def check_nap_consistency(scan_results):
    nap_variants = []
    for result in scan_results:
        biz = result["business"]
        if biz["nap_detected"]:
            nap_variants.append({
                "name": biz["name"],
                "phone": biz["phone"],
                "address": biz["address"]
            })

    # Check for inconsistencies
    unique_phones = {v["phone"] for v in nap_variants}
    if len(unique_phones) > 1:
        return {"consistent": False, "issue": "Multiple phone numbers"}
    return {"consistent": True}
```

### 3. Schema Markup Validator

```python
def validate_local_schema(business):
    issues = []

    if not business["localbusiness_schema_detected"]:
        issues.append({
            "severity": "high",
            "message": "Missing LocalBusiness schema"
        })

    if business["nap_detected"] and not business["localbusiness_schema_detected"]:
        issues.append({
            "severity": "medium",
            "message": "NAP present but not in schema markup"
        })

    if not business["google_business_hint"]:
        issues.append({
            "severity": "low",
            "message": "No Google Business Profile link detected"
        })

    return issues
```

## Testing

### Test Script

```python
import requests

def test_local_signals(url):
    response = requests.post(
        "http://localhost:8001/api/v1/orchestrator/run",
        json={"url": url, "features": {}}
    )

    business = response.json()["business"]

    print(f"URL: {url}")
    print(f"NAP Detected: {business['nap_detected']}")
    print(f"LocalBusiness Schema: {business['localbusiness_schema_detected']}")
    print(f"Organization Schema: {business['organization_schema_detected']}")
    print(f"Google Hint: {business['google_business_hint']}")
    print(f"Apple Hint: {business['apple_business_connect_hint']}")

    if business['nap_detected']:
        print(f"Name: {business['name']}")
        print(f"Phone: {business['phone']}")
        print(f"Address: {business['street_address']}, {business['city']}, {business['state']} {business['postal_code']}")

# Test with known local business sites
test_local_signals("https://example-law-firm.com")
test_local_signals("https://example-restaurant.com")
```

### Expected Test Results

| URL Type               | nap_detected | localbusiness_schema | google_hint |
| ---------------------- | ------------ | -------------------- | ----------- |
| Law firm with full NAP | ✅ true      | ✅ true              | ✅ true     |
| Restaurant with schema | ✅ true      | ✅ true              | ⚠️ varies   |
| Online-only business   | ❌ false     | ❌ false             | ❌ false    |
| Blog/content site      | ❌ false     | ❌ false             | ❌ false    |

## Scoring Integration

These flags are used in GEO scoring (see `scoring_rules.yaml`):

```yaml
geo_dimensions:
  - name: "Local Signals"
    rules:
      - type: "nap_detected"
        field: "business.nap_detected"
        points: 30

  - name: "Schema Quality"
    rules:
      - type: "localbusiness_schema"
        field: "business.localbusiness_schema_detected"
        points: 20
      - type: "google_business_linked"
        field: "business.google_business_hint"
        points: 10
```

## Best Practices

1. **Always check boolean flags first** for quick filtering
2. **Use granular address fields** for display and validation
3. **Combine with PSI local speed** for complete local SEO score
4. **Track changes over time** to catch NAP inconsistencies
5. **Use platform hints** to guide citation building recommendations

## Troubleshooting

**NAP detected but no schema flag?**
→ Business info is in HTML but not in structured data. Recommend adding LocalBusiness schema.

**Schema flag but no NAP detected?**
→ Schema exists but may be incomplete or malformed. Check individual address fields.

**No flags but business clearly exists?**
→ Check regex patterns may need adjustment for international formats.

## Future Enhancements

- [ ] Support for international phone/address formats
- [ ] Bing Places detection
- [ ] Yelp/TripAdvisor citation hints
- [ ] Multi-location business detection
- [ ] NAP consistency scoring across pages
- [ ] Service area radius detection from schema

---

**Last Updated:** 2025-10-30  
**Version:** 1.0.0
