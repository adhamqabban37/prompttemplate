"""Simple test of scoring rules YAML loading."""
import yaml
from pathlib import Path

# Load the rules
rules_path = Path(__file__).parent.parent / "scoring_rules.yaml"
print(f"Loading rules from: {rules_path}")
print(f"File exists: {rules_path.exists()}")

if rules_path.exists():
    with open(rules_path, "r", encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    
    print(f"\n✓ Rules loaded successfully!")
    print(f"  - AEO dimensions: {len(rules.get('aeo_dimensions', []))}")
    print(f"  - GEO dimensions: {len(rules.get('geo_dimensions', []))}")
    print(f"  - Weakness rules: {len(rules.get('weaknesses', []))}")
    
    print("\n📊 AEO Dimensions:")
    for dim in rules.get('aeo_dimensions', []):
        print(f"  • {dim['name']}")
        print(f"    Base score: {dim.get('base_score', 0)}")
        print(f"    Rules: {len(dim.get('rules', []))}")
    
    print("\n📍 GEO Dimensions:")
    for dim in rules.get('geo_dimensions', []):
        print(f"  • {dim['name']}")
        print(f"    Base score: {dim.get('base_score', 0)}")
        print(f"    Rules: {len(dim.get('rules', []))}")
    
    print("\n⚠️  Weakness Checks:")
    for weak in rules.get('weaknesses', []):
        print(f"  • {weak['title']} ({weak['impact']})")
    
    print("\n✅ YAML structure is valid!")
else:
    print("❌ Rules file not found!")
