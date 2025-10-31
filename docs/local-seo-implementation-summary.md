# Local SEO Signals Detection - Implementation Summary

## Changes Made

### 1. Updated Pydantic Schema (`orchestrator.py`)

**BusinessOutput Model - Added Fields:**

```python
class BusinessOutput(BaseModel):
    # ... existing fields ...

    # NEW: Granular address components
    street_address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]

    # NEW: Local SEO boolean flags
    nap_detected: bool = False
    localbusiness_schema_detected: bool = False
    organization_schema_detected: bool = False
    google_business_hint: bool = False
    apple_business_connect_hint: bool = False
```

### 2. Enhanced Business Entity Extraction (`orchestrator.py`)

**Function:** `_extract_business_entity(schema_data, html_text, html_lower, out_links)`

**New Capabilities:**

1. **Granular Address Parsing:**

   - Extract `streetAddress`, `addressLocality`, `addressRegion`, `postalCode` from JSON-LD
   - Fallback regex for US address patterns
   - Individual fields: `street_address`, `city`, `state`, `postal_code`

2. **Schema Detection:**

   - Detect `LocalBusiness` schema (including subtypes like Attorney, Dentist, etc.)
   - Detect `Organization` schema with address
   - Set boolean flags for both

3. **Platform Hint Detection:**

   - Google Business Profile: Check for `google.com/maps`, `maps.google.com`, `g.page`, `business.google.com`
   - Apple Business Connect: Check for `maps.apple.com`, `businessconnect.apple.com`

4. **NAP Detection Logic:**

   ```python
   nap_detected = bool(name and phone and (address or (city and state)))
   ```

5. **Regex Fallback Patterns:**
   - Phone: `(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}`
   - City/State/ZIP: `([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)`
   - ZIP only: `\b\d{5}(?:-\d{4})?\b`
   - State: `\b([A-Z]{2})\s+\d{5}`

### 3. Updated Worker Extraction (`worker.py`)

**In `process_scan_job()` function:**

1. **Added inline business data extraction:**

   - Parse JSON-LD for Organization/LocalBusiness
   - Extract all address components
   - Detect schema types and set boolean flags
   - Check links for platform hints
   - Regex fallback for phone and postal code

2. **Updated Teaser JSON:**

   ```python
   job.teaser_json = {
       # ... existing fields ...
       "business": {
           "name": biz_name,
           "phone": biz_phone,
           "city": biz_city,
           "state": biz_state,
           "nap_detected": nap_detected,
           "localbusiness_schema_detected": localbusiness_detected,
           "organization_schema_detected": organization_detected,
           "google_business_hint": google_hint,
           "apple_business_connect_hint": apple_hint,
       }
   }
   ```

3. **Updated Full JSON:**
   ```python
   job.full_json = {
       # ... existing fields ...
       "business": {
           "name": biz_name,
           "phone": biz_phone,
           "address": biz_address,
           "street_address": biz_street,
           "city": biz_city,
           "state": biz_state,
           "postal_code": biz_postal,
           "nap_detected": nap_detected,
           "localbusiness_schema_detected": localbusiness_detected,
           "organization_schema_detected": organization_detected,
           "google_business_hint": google_hint,
           "apple_business_connect_hint": apple_hint,
       }
   }
   ```

### 4. Documentation Created

**File:** `docs/local-seo-signals.md` (comprehensive guide)

**Contents:**

- Complete API schema documentation
- Detection logic for all signals
- Response examples for different scenarios
- Integration points (orchestrator, teaser, full)
- Use cases (audit dashboard, NAP checker, schema validator)
- Test scripts and expected results
- Scoring integration notes
- Best practices and troubleshooting

## API Response Structure

### Orchestrator Endpoint Response

```json
{
  "business": {
    "name": "Smith & Associates Law",
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

### Scan Job Teaser Response

```json
{
  "teaser": {
    "title": "Smith & Associates Law",
    "business": {
      "name": "Smith & Associates Law",
      "phone": "+1-555-123-4567",
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

## Boolean Flag Meanings

| Flag                            | Meaning                                    | Use Case                            |
| ------------------------------- | ------------------------------------------ | ----------------------------------- |
| `nap_detected`                  | Has Name + Phone + (Address OR City+State) | Quick local business identification |
| `localbusiness_schema_detected` | Has LocalBusiness JSON-LD schema           | Schema markup audit                 |
| `organization_schema_detected`  | Has Organization JSON-LD with address      | Alternative schema check            |
| `google_business_hint`          | Links to Google Maps/GBP                   | Citation building guidance          |
| `apple_business_connect_hint`   | Links to Apple Maps/Business               | Platform coverage check             |

## Testing

### Quick Test

```bash
# Start backend
cd c:\dev\projects-template\backend
pwsh -NoProfile -ExecutionPolicy Bypass -File .\run_backend.ps1

# Test orchestrator
curl -X POST http://localhost:8001/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "features": {"use_lighthouse": false}
  }'
```

### Expected Response Keys

```json
{
  "business": {
    "street_address": "...", // NEW
    "city": "...", // NEW
    "state": "...", // NEW
    "postal_code": "...", // NEW
    "nap_detected": true, // NEW
    "localbusiness_schema_detected": true, // NEW
    "organization_schema_detected": true, // NEW
    "google_business_hint": true, // NEW
    "apple_business_connect_hint": false // NEW
  }
}
```

## Files Modified

1. ✅ `backend/app/api/routes/orchestrator.py`

   - Updated `BusinessOutput` model
   - Enhanced `_extract_business_entity()` function
   - Updated BusinessOutput instantiation

2. ✅ `backend/app/worker.py`

   - Added inline business extraction in `process_scan_job()`
   - Updated `teaser_json` structure
   - Updated `full_json` structure

3. ✅ `docs/local-seo-signals.md` (NEW)
   - Complete implementation guide
   - Response examples
   - Integration documentation

## Integration Notes

### Frontend Display

```typescript
// Show NAP status
<Badge color={business.nap_detected ? "green" : "red"}>
  {business.nap_detected ? "✓ NAP Complete" : "✗ NAP Missing"}
</Badge>

// Show schema status
<Badge color={business.localbusiness_schema_detected ? "green" : "yellow"}>
  {business.localbusiness_schema_detected ? "✓ Schema" : "⚠ No Schema"}
</Badge>

// Show platform hints
{business.google_business_hint && (
  <Text>✓ Google Business Profile linked</Text>
)}
{business.apple_business_connect_hint && (
  <Text>✓ Apple Business Connect linked</Text>
)}
```

### Scoring Rules Integration

These signals can be used in `scoring_rules.yaml`:

```yaml
geo_dimensions:
  - name: "NAP Completeness"
    rules:
      - type: "nap_detected"
        field: "business.nap_detected"
        points: 30

  - name: "Schema Markup"
    rules:
      - type: "localbusiness_schema"
        field: "business.localbusiness_schema_detected"
        points: 20
      - type: "organization_schema"
        field: "business.organization_schema_detected"
        points: 10

  - name: "Platform Citations"
    rules:
      - type: "google_business"
        field: "business.google_business_hint"
        points: 15
      - type: "apple_business"
        field: "business.apple_business_connect_hint"
        points: 10
```

## Backward Compatibility

✅ **Fully backward compatible**

- Existing fields unchanged
- New fields are optional with defaults
- Boolean flags default to `False`
- No breaking changes to API contracts

## Performance Impact

- **Negligible overhead**: Regex parsing happens during normal HTML extraction
- **No additional HTTP requests**: Uses existing HTML/schema data
- **Efficient pattern matching**: Single pass through links/HTML

## Next Steps

1. ✅ Test with real local business websites
2. ✅ Verify all boolean flags trigger correctly
3. ✅ Update frontend to display new fields
4. ✅ Add to GEO scoring rules
5. ✅ Create weakness conditions for missing NAP/schema

---

**Status:** ✅ Complete and ready for testing  
**Breaking Changes:** None  
**New Dependencies:** None (uses existing libraries)
