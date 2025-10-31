# Scoring Rules Configuration Guide

## Overview

XenlixAI's AEO (Answer Engine Optimization) and GEO (Geographic/Local SEO) scoring logic is now **data-driven** and configured via the `backend/scoring_rules.yaml` file. This allows you to adjust scoring weights, thresholds, and rules without modifying Python code.

## File Location

```
backend/
  ├── scoring_rules.yaml          # Main rules configuration
  ├── app/
  │   └── api/
  │       └── routes/
  │           └── orchestrator.py  # Loads and applies rules
```

## How It Works

1. **Startup**: The orchestrator module loads `scoring_rules.yaml` on first use
2. **Scoring**: When analyzing a URL, the `_compute_scores` function applies rules dynamically
3. **Output**: Returns AEO/GEO scores with triggered rules and weaknesses

## YAML Structure

### AEO Dimensions

Each AEO dimension has:

- `name`: Display name (e.g., "Answerability")
- `rationale`: Brief explanation
- `base_score`: Starting points (before rule bonuses)
- `rules`: List of scoring rules to apply
- `max_score`: Cap at 100

**Example:**

```yaml
aeo_dimensions:
  - name: "Answerability"
    rationale: "FAQ and Q&A signals"
    base_score: 40
    rules:
      - type: "faq_count"
        field: "faq_count"
        multiplier: 20
        description: "Points per FAQ schema detected"
      - type: "question_headings"
        field: "headings.h2"
        multiplier: 10
        filter: "question_patterns"
        description: "H2s starting with question words"
    max_score: 100
```

### GEO Dimensions

Similar structure to AEO, but focused on local SEO factors:

```yaml
geo_dimensions:
  - name: "Local Signals"
    rationale: "Address and map embeds"
    base_score: 30
    rules:
      - type: "address_present"
        field: "business.address"
        points: 20
        description: "Physical address detected"
      - type: "map_embed"
        field: "html_lower"
        points: 10
        condition: "contains_maps_google"
        description: "Google Maps embed detected"
    max_score: 100
```

### Weaknesses

Conditions that trigger actionable warnings:

```yaml
weaknesses:
  - title: "Missing LocalBusiness schema"
    impact: "high"
    condition:
      field: "schema_types"
      operator: "not_contains"
      value: "localbusiness"
    evidence: ["schema_types lacks LocalBusiness"]
    fix_summary: "Add LocalBusiness JSON-LD with name, address, phone, geo."
```

## Rule Types

### Field References

Use dot notation to access nested data:

- `"faq_count"` → page FAQ count
- `"business.name"` → business name from NAP extraction
- `"headings.h2"` → list of H2 headings
- `"psi.performance"` → PSI performance score

### Operators

**Condition operators for weaknesses:**

- `not_present`: Field is None/empty
- `not_contains`: List doesn't contain value
- `less_than`: Numeric field below threshold
- `equals`: Field equals exact value

### Rule Types

**AEO/GEO Scoring:**

- `faq_count`: Multiply FAQ count by multiplier
- `question_headings`: Count H2s matching question patterns
- `schema_diversity`: Points per unique schema type
- `local_business_bonus`: Fixed bonus if LocalBusiness present
- `business_name/phone/address`: Fixed points if field present
- `internal_links`: Formula-based (e.g., `min(50, value // 10)`)
- `text_length`: Formula-based (e.g., `min(70, value // 800)`)
- `about_link`: Points if "about" in links
- `review_content`: Points if "review" in HTML
- `citation_sources`: Count matches in target list
- `psi_performance`: Formula with fallback (e.g., `value // 2`)

## Editing Guide

### Changing Weights

To adjust how much a factor contributes:

```yaml
# Before: FAQ count worth 20 points each
- type: "faq_count"
  multiplier: 20

# After: FAQ count worth 30 points each
- type: "faq_count"
  multiplier: 30
```

### Changing Thresholds

To modify weakness triggers:

```yaml
# Before: Warn if performance < 70
- title: "Performance could be improved"
  condition:
    field: "psi.performance"
    operator: "less_than"
    value: 70

# After: Warn if performance < 80
- title: "Performance could be improved"
  condition:
    field: "psi.performance"
    operator: "less_than"
    value: 80
```

### Adding New Rules

1. **Add to appropriate dimension:**

```yaml
aeo_dimensions:
  - name: "Schema Coverage & Quality"
    rules:
      # ... existing rules ...
      - type: "howto_bonus"
        field: "schema_types"
        bonus: 5
        condition: "contains_howto"
        description: "Bonus for HowTo schema"
```

2. **Implement rule type in `orchestrator.py`:**

```python
elif rule_type == "howto_bonus":
    schema_types = value or []
    if any(s.lower() == "howto" for s in schema_types):
        points = rule.get("bonus", 0)
        evidence.append("HowTo schema present")
```

3. **Test with sample data**

### Adding New Weaknesses

```yaml
weaknesses:
  - title: "No contact form detected"
    impact: "low"
    condition:
      field: "html_lower"
      operator: "not_contains"
      value: "contact"
    evidence: ["No contact form on page"]
    fix_summary: "Add a prominent contact form for user inquiries."
```

## Testing Changes

1. **Validate YAML syntax:**

```bash
cd backend
python test_yaml_load.py
```

2. **Run scoring tests:**

```bash
python -m scripts.test_scoring_rules
```

3. **Test with real URL:**

```bash
# Start backend
.\run_backend.ps1

# Call orchestrator endpoint
curl -X POST http://localhost:8001/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://example.com", "features": {"use_lighthouse": true}}'
```

## Best Practices

1. **Keep base scores meaningful**: They should reflect minimum quality (30-50 range)
2. **Cap contributions**: Use `max_contribution` to prevent single factors dominating
3. **Document every rule**: Use `description` field for clarity
4. **Test incrementally**: Change one rule at a time and verify
5. **Preserve evidence**: Evidence lists help debug scoring issues
6. **Balance dimensions**: Aim for similar max scores across dimensions

## Data Sources

The scoring system uses these data fields extracted during URL analysis:

**Page Data:**

- `faq_count`: Number of FAQPage schemas
- `headings`: Dict with h1, h2, h3 lists
- `schema_types`: List of detected schema types
- `internal_links`: Count of internal links
- `text_len`: Main text length in characters
- `links_text`: List of link anchor texts
- `html_lower`: Lowercased HTML for pattern matching
- `out_links`: List of external URLs

**Business Data (NAP extraction):**

- `name`: Business name
- `phone`: Phone number
- `email`: Email address
- `address`: Full postal address
- `service_areas`: List of served locations

**PSI Data:**

- `performance`: Lighthouse performance score (0-100)
- `seo`: SEO score (0-100)
- Web Vitals: LCP, FID, CLS

## Troubleshooting

**Rules not loading:**

- Check `backend/scoring_rules.yaml` exists
- Validate YAML syntax (no tabs, proper indentation)
- Check backend logs for parsing errors

**Scores seem wrong:**

- Add print statements in `_apply_rule` function
- Check evidence arrays in API response
- Verify field names match data structure

**New rule not working:**

- Implement handler in `_apply_rule` function
- Ensure rule type string matches exactly
- Test with known data that should trigger it

## Example: Adding Custom Citation Sources

```yaml
# 1. Update citation_sources section
citation_sources:
  - "yelp"
  - "google.com/maps"
  - "facebook.com"
  - "linkedin.com" # NEW
  - "bbb.org"
  - "trustpilot.com" # NEW

# 2. Update the rule (no code change needed!)
aeo_dimensions:
  - name: "Citations/Backlinks (light)"
    rules:
      - type: "citation_sources"
        field: "out_links"
        multiplier: 15 # Reduced from 20 since more sources now
        targets:
          - "yelp"
          - "google.com/maps"
          - "facebook.com"
          - "linkedin.com"
          - "bbb.org"
          - "trustpilot.com"
```

## Versioning

When making significant changes:

1. Copy `scoring_rules.yaml` to `scoring_rules_v1.yaml` (backup)
2. Document changes in git commit message
3. Update this guide with new rule types
4. Notify team of scoring methodology changes

---

**Next Steps:**

- Review current scores against real sites
- Tune weights based on correlation with actual rankings
- Add more nuanced rules (e.g., brand mentions, social proof)
- Consider A/B testing different rule sets
