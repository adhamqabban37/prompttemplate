# Scoring Rules Quick Reference

## 🎯 Quick Edits

### Change FAQ Value

```yaml
# File: backend/scoring_rules.yaml
# Line: ~12
- type: "faq_count"
  multiplier: 20 # ← Change this number
```

### Change Performance Threshold

```yaml
# File: backend/scoring_rules.yaml
# Line: ~198
- title: "Performance could be improved"
  condition:
    value: 70 # ← Raise to 80 for stricter check
```

### Add Citation Source

```yaml
# File: backend/scoring_rules.yaml
# Line: ~100
- type: "citation_sources"
  targets:
    - "yelp"
    - "google.com/maps"
    - "linkedin.com" # ← Add new source
```

## 📊 Score Breakdown

### AEO Dimensions (7)

1. **Answerability** (base: 40) - FAQ schemas + question headings
2. **Schema Coverage** (base: 30) - Unique schema types + LocalBusiness bonus
3. **Entity/NAP** (base: 50) - Name/Phone/Address presence
4. **Topical Authority** (base: 30) - Internal link count
5. **Content Quality** (base: 30) - Text length
6. **E-E-A-T** (base: 50) - About links + reviews
7. **Citations** (base: 20) - Citation source links

### GEO Dimensions (6)

1. **Local Signals** (base: 30) - Address + map embeds
2. **Service Area** (base: 30) - Service areas defined
3. **Location Schema** (base: 30) - PostalAddress/Geo schemas
4. **NAP Prominence** (base: 40) - Phone/Email clickable
5. **Local Reviews** (base: 30) - Review mentions
6. **Local Speed** (base: 50) - PSI performance / 2

## 🔧 Common Tasks

### Test Changes

```bash
cd backend
python test_yaml_load.py           # Validate syntax
python -m scripts.test_scoring_rules  # Test logic
```

### Apply Changes

1. Edit `backend/scoring_rules.yaml`
2. Save file
3. Restart backend: `.\run_backend.ps1`
4. Test with real URL

### View Scores

```bash
curl -X POST http://localhost:8001/api/v1/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://example.com", "features": {}}'
```

## 📝 Rule Anatomy

```yaml
- name: "Dimension Name"
  rationale: "Why this matters"
  base_score: 40 # Starting points
  rules:
    - type: "rule_type"
      field: "data.field" # Dot notation
      multiplier: 10 # Points per unit
      description: "What it does"
  max_score: 100 # Cap at this
```

## ⚠️ Weakness Anatomy

```yaml
- title: "Issue description"
  impact: "high" # high/med/low
  condition:
    field: "data.field"
    operator: "less_than" # not_present, not_contains, less_than, equals
    value: 70
  evidence: ["Context clue"]
  fix_summary: "How to fix it"
```

## 🎛️ Tuning Tips

**Increase importance:**

- Raise `multiplier` (e.g., 20 → 30)
- Raise `base_score` (e.g., 30 → 40)

**Decrease importance:**

- Lower `multiplier` (e.g., 20 → 10)
- Add `max_contribution` cap

**Make stricter:**

- Raise threshold values
- Add new weakness conditions

**Make lenient:**

- Lower threshold values
- Remove weakness rules

## 📚 Full Documentation

- **Complete Guide**: `docs/scoring-rules-guide.md`
- **Refactor Summary**: `docs/scoring-refactor-summary.md`
- **Rules File**: `backend/scoring_rules.yaml`

## 🚨 Troubleshooting

**Syntax error?**
→ Run `python test_yaml_load.py` to find it

**Scores seem off?**
→ Check `evidence` arrays in API response

**Rule not working?**
→ Verify `field` name matches data structure

**Backend won't start?**
→ Check for YAML indentation (spaces only, no tabs)

---

**Pro Tip:** Copy `scoring_rules.yaml` to `scoring_rules_backup.yaml` before major changes!
