# Local SEO Signal Detection - Code Flow

## Detection Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    URL Analysis Request                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Fetch HTML Content                         │
│  • fetch_html(url) → raw HTML                                   │
│  • BeautifulSoup parsing                                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Extract Structured Data                        │
│  • extruct.extract() → JSON-LD, Microdata                      │
│  • Parse schema_raw dict                                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│   Primary: JSON-LD       │  │   Fallback: Regex        │
│   Schema Extraction      │  │   Pattern Matching       │
└──────────────────────────┘  └──────────────────────────┘
                │                         │
                ▼                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NAP Field Extraction                         │
│                                                                 │
│  From JSON-LD:                 From Regex:                     │
│  ┌──────────────────┐          ┌──────────────────┐           │
│  │ @type checks:    │          │ Phone pattern:   │           │
│  │ • LocalBusiness  │          │ \(?\d{3}\)?...   │           │
│  │ • Organization   │          │                  │           │
│  └──────────────────┘          │ ZIP pattern:     │           │
│                                 │ \d{5}(-\d{4})?   │           │
│  ┌──────────────────┐          │                  │           │
│  │ address fields:  │          │ City/State:      │           │
│  │ • streetAddress  │          │ City, ST ZIP     │           │
│  │ • addressLocality│          └──────────────────┘           │
│  │ • addressRegion  │                                          │
│  │ • postalCode     │                                          │
│  └──────────────────┘                                          │
│                                                                 │
│  ┌──────────────────┐                                          │
│  │ contact fields:  │                                          │
│  │ • name           │                                          │
│  │ • telephone      │                                          │
│  │ • email          │                                          │
│  └──────────────────┘                                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Schema Type Detection                          │
│                                                                 │
│  For each JSON-LD item:                                        │
│  ┌────────────────────────────────────┐                        │
│  │ if @type contains "LocalBusiness": │                        │
│  │   → localbusiness_schema_detected = True                   │
│  │                                    │                        │
│  │ if @type == "Organization":        │                        │
│  │   → organization_schema_detected = True                    │
│  └────────────────────────────────────┘                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Platform Hint Detection                        │
│                                                                 │
│  Scan all href links + HTML content:                           │
│  ┌────────────────────────────────────┐                        │
│  │ Contains "google.com/maps"?        │                        │
│  │ Contains "maps.google.com"?        │                        │
│  │ Contains "g.page"?                 │                        │
│  │ → google_business_hint = True      │                        │
│  │                                    │                        │
│  │ Contains "maps.apple.com"?         │                        │
│  │ Contains "businessconnect.apple"?  │                        │
│  │ → apple_business_connect_hint = True                       │
│  └────────────────────────────────────┘                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NAP Detection Logic                          │
│                                                                 │
│  ┌────────────────────────────────────────────────┐            │
│  │ nap_detected = bool(                           │            │
│  │     name AND                                   │            │
│  │     phone AND                                  │            │
│  │     (address OR (city AND state))              │            │
│  │ )                                              │            │
│  └────────────────────────────────────────────────┘            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Return BusinessOutput                        │
│                                                                 │
│  {                                                              │
│    name: "Example Business",                                   │
│    phone: "555-1234",                                           │
│    address: "123 Main St, City, ST 12345",                     │
│    street_address: "123 Main St",                              │
│    city: "City",                                                │
│    state: "ST",                                                 │
│    postal_code: "12345",                                        │
│    nap_detected: true,                                          │
│    localbusiness_schema_detected: true,                        │
│    organization_schema_detected: true,                         │
│    google_business_hint: true,                                  │
│    apple_business_connect_hint: false                          │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

## Key Code Locations

### 1. Schema Model Definition

**File:** `backend/app/api/routes/orchestrator.py:100`

```python
class BusinessOutput(BaseModel):
    # ... fields with boolean flags
```

### 2. Main Extraction Function

**File:** `backend/app/api/routes/orchestrator.py:406`

```python
def _extract_business_entity(schema_data, html_text, html_lower, out_links):
    # Primary: Parse JSON-LD
    for item in schema_data.get("json-ld", []):
        if item.get("@type") in ["Organization", "LocalBusiness"]:
            # Extract NAP fields

    # Fallback: Regex patterns
    if not phone:
        phone = re.search(r"phone_pattern", html_text)

    # Schema detection
    localbusiness_detected = "localbusiness" in schema_types

    # Platform hints
    google_hint = "google.com/maps" in all_links

    # NAP logic
    nap_detected = bool(name and phone and (address or (city and state)))

    return {...}
```

### 3. Function Call

**File:** `backend/app/api/routes/orchestrator.py:928`

```python
biz_data = _extract_business_entity(schema_raw, html, html_lower, out_links)
```

### 4. Worker Integration

**File:** `backend/app/worker.py:90-170`

```python
def process_scan_job(job_id, url, user_id=None):
    # Inline extraction
    schema_raw = extruct.extract(html, ...)
    business_data = {
        # ... extract fields
        "nap_detected": bool(name and phone and address),
        "localbusiness_schema_detected": ...,
        # ... set flags
    }

    # Persist to teaser/full
    job.teaser_json = {"business": {...}}
    job.full_json = {"business": {...}}
```

## Regex Patterns Reference

```python
# Phone (US format)
r"(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
# Examples: 555-1234, (555) 123-4567, +1-555-123-4567

# Email
r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
# Examples: contact@example.com, info@business.org

# City, State, ZIP
r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)"
# Examples: San Francisco, CA 94102

# ZIP only
r"\b\d{5}(?:-\d{4})?\b"
# Examples: 12345, 12345-6789

# State before ZIP
r"\b([A-Z]{2})\s+\d{5}"
# Examples: CA 94102, NY 10001
```

## Schema Type Detection Logic

```python
# LocalBusiness detection (case-insensitive, substring match)
if "localbusiness" in str(schema_type).lower():
    localbusiness_schema_detected = True

# Detects:
# - "LocalBusiness"
# - "Attorney" (subtype of LocalBusiness)
# - "Dentist" (subtype of LocalBusiness)
# - "Restaurant" (subtype of LocalBusiness)
# - Any LocalBusiness subtype

# Organization detection (exact match)
if str(schema_type).lower() == "organization":
    organization_schema_detected = True
```

## Platform Link Patterns

```python
# Google Business Profile hints
google_patterns = [
    "google.com/maps",
    "maps.google.com",
    "g.page/",                    # Short link format
    "business.google.com"
]

# Apple Business Connect hints
apple_patterns = [
    "maps.apple.com",
    "businessconnect.apple.com"
]

# Check in: href attributes + lowercased HTML
all_links = " ".join(out_links + [html_lower])
google_hint = any(pattern in all_links for pattern in google_patterns)
apple_hint = any(pattern in all_links for pattern in apple_patterns)
```

## Decision Tree

```
HTML Content
    │
    ├─► Has JSON-LD?
    │   ├─► Yes → Parse @type
    │   │   ├─► LocalBusiness? → Set flag + Extract NAP
    │   │   └─► Organization? → Set flag + Extract NAP
    │   └─► No → Skip to regex
    │
    ├─► Has phone in schema?
    │   ├─► Yes → Use schema phone
    │   └─► No → Regex fallback
    │
    ├─► Has address components?
    │   ├─► Yes → Extract streetAddress, city, state, postal
    │   └─► No → Regex fallback for city/state/zip
    │
    ├─► Links contain Google Maps?
    │   └─► Yes → google_business_hint = True
    │
    └─► Links contain Apple Maps?
        └─► Yes → apple_business_connect_hint = True
```

## Priority Order (First Match Wins)

1. **Name:** JSON-LD `name` → null
2. **Phone:** JSON-LD `telephone` → Regex phone pattern → null
3. **Address:** JSON-LD `address.streetAddress` → null
4. **City:** JSON-LD `address.addressLocality` → Regex city pattern → null
5. **State:** JSON-LD `address.addressRegion` → Regex state pattern → null
6. **Postal:** JSON-LD `address.postalCode` → Regex ZIP pattern → null

## Testing Checklist

- [ ] Local business with complete LocalBusiness schema → All flags true
- [ ] Business with Organization but no LocalBusiness → Only org flag true
- [ ] Business with NAP in HTML but no schema → NAP detected, no schema flags
- [ ] Page with Google Maps embed → google_business_hint true
- [ ] Page with Apple Maps link → apple_business_connect_hint true
- [ ] Non-business page → All flags false
- [ ] Partial NAP (name + phone only) → nap_detected false
- [ ] International format (test graceful failure) → Regex fallback

---

**Legend:**

- ✅ Primary extraction path (JSON-LD)
- 🔄 Fallback path (Regex)
- ⚡ Boolean flag computation
- 📦 Final output structure
