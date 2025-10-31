# Scoring Rules Refactoring Summary

**Date:** 2025-01-XX  
**Status:** ✅ Complete

## What Changed

Refactored XenlixAI's AEO/GEO scoring logic from hardcoded Python to a **data-driven YAML configuration** system.

## Files Modified

### Created

1. **`backend/scoring_rules.yaml`** (new)

   - 400+ lines of scoring rules configuration
   - 7 AEO dimensions with base scores + rule multipliers
   - 6 GEO dimensions with local SEO factors
   - 6 weakness conditions with impact levels
   - Fully documented with descriptions

2. **`backend/scripts/test_scoring_rules.py`** (new)

   - Comprehensive test suite for rules system
   - Tests loading, scoring with sample data, edge cases
   - Run: `python -m scripts.test_scoring_rules`

3. **`backend/test_yaml_load.py`** (new)

   - Simple YAML validation script
   - Verifies rules file structure
   - Run: `python test_yaml_load.py`

4. **`docs/scoring-rules-guide.md`** (new)
   - Complete guide to editing scoring rules
   - Rule type reference
   - Testing procedures
   - Best practices

### Modified

1. **`backend/app/api/routes/orchestrator.py`**
   - Added imports: `yaml`, `Path`
   - Added `_load_scoring_rules()` function (loads YAML at startup)
   - Added `_get_nested_value()` helper (dot notation field access)
   - Added `_apply_rule()` function (evaluates single rule)
   - Replaced entire `_compute_scores()` function with data-driven version

## What Stayed the Same

- **API contracts**: Input/output schemas unchanged
- **Data extraction**: Still uses same page/business/PSI data
- **Pydantic models**: `ScoreDimension`, `ScoresAEO`, `ScoresGEO`, `WeaknessItem` unchanged
- **Endpoints**: `/orchestrator/run` still works identically

## How It Works Now

### Before (Hardcoded)

```python
# Answerability
faq_count = page.get("faq_count", 0)
h2 = page.get("headings", {}).get("h2", [])
q_heads = [h for h in h2 if "?" in h or h.lower().startswith(("what", "how", "why", "when", "where"))]
score_ans = min(100, 40 + faq_count * 20 + len(q_heads) * 10)
dims_aeo.append(ScoreDimension(name="Answerability", score=score_ans, ...))
```

### After (Data-Driven)

**YAML:**

```yaml
aeo_dimensions:
  - name: "Answerability"
    base_score: 40
    rules:
      - type: "faq_count"
        field: "faq_count"
        multiplier: 20
      - type: "question_headings"
        field: "headings.h2"
        multiplier: 10
```

**Python:**

```python
rules_config = _load_scoring_rules()
for dim_config in rules_config.get("aeo_dimensions", []):
    score = dim_config.get("base_score", 0)
    for rule in dim_config.get("rules", []):
        rule_points, rule_evidence = _apply_rule(rule, data, rules_config)
        score += rule_points
    # ...
```

## Benefits

1. **No Code Changes for Tuning**: Adjust weights in YAML, restart backend
2. **Easier Testing**: A/B test different rule sets by swapping files
3. **Version Control**: Track scoring methodology changes in git
4. **Non-Dev Editing**: Product/SEO team can tune scores directly
5. **Self-Documenting**: YAML includes descriptions and rationales
6. **Extensible**: Add new rules without touching orchestrator.py

## Migration Notes

### Backward Compatibility

✅ **Fully backward compatible**

- Same input/output schemas
- Same score ranges (0-100)
- Same dimension names
- Same weakness messages

### Performance

⚡ **Negligible overhead**

- Rules loaded once at startup (cached in `_SCORING_RULES`)
- No per-request YAML parsing
- Rule evaluation is simple field lookups + arithmetic

## Testing

### Automated Tests

```bash
# Validate YAML structure
cd backend
python test_yaml_load.py

# Test scoring logic
python -m scripts.test_scoring_rules
```

### Manual Testing

```bash
# Start backend
.\run_backend.ps1

# Test orchestrator endpoint
curl -X POST http://localhost:8001/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://example.com",
    "features": {"use_lighthouse": true, "use_keybert": true}
  }'
```

Expected response includes:

- `scores.aeo.total`: 0-100
- `scores.aeo.dimensions[]`: Array of 7 dimensions
- `scores.geo.total`: 0-100
- `scores.geo.dimensions[]`: Array of 6 dimensions
- `weaknesses[]`: Array of triggered issues

## Rule Types Implemented

### AEO Rules

1. `faq_count` - FAQ schema detection
2. `question_headings` - H2s with question patterns
3. `schema_diversity` - Unique schema type count
4. `local_business_bonus` - LocalBusiness schema bonus
5. `business_name/phone/address` - NAP field presence
6. `internal_links` - Internal link depth
7. `text_length` - Content length proxy
8. `about_link` - About page link detection
9. `review_content` - Review mentions
10. `citation_sources` - Known citation sites

### GEO Rules

1. `address_present` - Physical address detection
2. `map_embed` - Google Maps embed detection
3. `service_areas` - Service area definition
4. `location_schema_types` - Geo/PostalAddress schemas
5. `phone_clickable` - Phone number presence
6. `email_clickable` - Email presence
7. `review_mentions` - Review content detection
8. `psi_performance` - PSI score integration

### Weakness Conditions

1. `not_present` - Field is None/empty
2. `not_contains` - List doesn't contain value
3. `less_than` - Numeric below threshold
4. `equals` - Exact match

## Future Enhancements

### Short Term

- [ ] Add more citation sources (LinkedIn, Trustpilot, etc.)
- [ ] Tune multipliers based on real-world correlation
- [ ] Add severity thresholds for weaknesses

### Medium Term

- [ ] Support for custom formulas via safe eval
- [ ] Multi-language question patterns
- [ ] Industry-specific rule sets

### Long Term

- [ ] A/B testing framework for rules
- [ ] ML-based weight optimization
- [ ] Rule recommendation engine

## Rollback Plan

If issues arise:

1. **Quick rollback** (keep old logic):

   ```python
   # In orchestrator.py, comment out new function
   # Uncomment old _compute_scores implementation
   ```

2. **Hot fix** (edit YAML only):

   - Adjust problematic rule multipliers
   - Restart backend
   - No code deploy needed

3. **Full revert** (git):
   ```bash
   git revert <commit-hash>
   ```

## Dependencies

- **PyYAML>=6.0.0** (already in `pyproject.toml`)
- No new external dependencies

## Documentation

- **Guide**: `docs/scoring-rules-guide.md` (400+ lines)
- **Rules**: `backend/scoring_rules.yaml` (fully commented)
- **Tests**: `backend/scripts/test_scoring_rules.py`

## Success Criteria

✅ Rules load from YAML at startup  
✅ Scores match original hardcoded logic  
✅ API response format unchanged  
✅ No performance regression  
✅ Documentation complete  
✅ Test coverage added

## Next Steps

1. **Deploy to dev**: Test with real URLs
2. **Tune weights**: Based on actual ranking correlation
3. **Team training**: Walk through YAML editing process
4. **Monitor metrics**: Watch for scoring anomalies
5. **Iterate**: Refine rules based on feedback

---

**Questions?** See `docs/scoring-rules-guide.md` or contact the dev team.
