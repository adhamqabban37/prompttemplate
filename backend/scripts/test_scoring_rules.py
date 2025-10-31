"""
Test script to verify scoring rules are loading and applying correctly.
Run from backend directory: python -m scripts.test_scoring_rules
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.api.routes.orchestrator import _load_scoring_rules, _compute_scores

def test_rules_loading():
    """Test that rules load from YAML file."""
    print("Testing rules loading...")
    rules = _load_scoring_rules()
    
    print(f"✓ Loaded {len(rules.get('aeo_dimensions', []))} AEO dimensions")
    print(f"✓ Loaded {len(rules.get('geo_dimensions', []))} GEO dimensions")
    print(f"✓ Loaded {len(rules.get('weaknesses', []))} weakness rules")
    
    # Show AEO dimension names
    print("\nAEO Dimensions:")
    for dim in rules.get("aeo_dimensions", []):
        print(f"  - {dim['name']}")
    
    # Show GEO dimension names
    print("\nGEO Dimensions:")
    for dim in rules.get("geo_dimensions", []):
        print(f"  - {dim['name']}")
    
    return rules


def test_scoring_computation():
    """Test scoring with sample data."""
    print("\n" + "="*60)
    print("Testing scoring computation...")
    print("="*60)
    
    # Sample page data
    page_data = {
        "faq_count": 2,
        "headings": {"h2": ["What services do we offer?", "How to contact us", "Our locations"]},
        "schema_types": ["Organization", "LocalBusiness", "FAQPage"],
        "internal_links": 35,
        "text_len": 2400,
        "links_text": ["Home", "About", "Services", "Contact"],
        "html_lower": "reviews from customers show we're trusted. maps.google embed here.",
        "out_links": ["https://yelp.com/biz/example", "https://facebook.com/example"],
    }
    
    # Sample business data
    biz_data = {
        "name": "Acme Law Firm",
        "phone": "+1-555-1234",
        "email": "info@acme.com",
        "address": "123 Main St, City, ST 12345",
        "service_areas": ["City", "County"],
    }
    
    # Sample PSI data
    psi_data = {
        "performance": 85,
        "seo": 95,
    }
    
    # Compute scores
    aeo_scores, geo_scores, weaknesses = _compute_scores(page_data, biz_data, psi_data)
    
    print(f"\n📊 AEO Total Score: {aeo_scores.total}/100")
    for dim in aeo_scores.dimensions:
        print(f"  {dim.name}: {dim.score}/100")
        if dim.evidence:
            print(f"    Evidence: {', '.join(str(e) for e in dim.evidence[:3])}")
    
    print(f"\n📍 GEO Total Score: {geo_scores.total}/100")
    for dim in geo_scores.dimensions:
        print(f"  {dim.name}: {dim.score}/100")
        if dim.evidence:
            print(f"    Evidence: {', '.join(str(e) for e in dim.evidence[:3])}")
    
    print(f"\n⚠️  Weaknesses Found: {len(weaknesses)}")
    for weak in weaknesses:
        print(f"  [{weak.impact.upper()}] {weak.title}")
        print(f"    Fix: {weak.fix_summary}")


def test_missing_data_scenario():
    """Test scoring with minimal/missing data."""
    print("\n" + "="*60)
    print("Testing with minimal data...")
    print("="*60)
    
    # Minimal page data
    page_data = {
        "faq_count": 0,
        "headings": {"h2": []},
        "schema_types": [],
        "internal_links": 5,
        "text_len": 400,
        "links_text": [],
        "html_lower": "",
        "out_links": [],
    }
    
    # Minimal business data
    biz_data = {
        "name": None,
        "phone": None,
        "email": None,
        "address": None,
        "service_areas": [],
    }
    
    # Minimal PSI data
    psi_data = {
        "performance": 45,
    }
    
    # Compute scores
    aeo_scores, geo_scores, weaknesses = _compute_scores(page_data, biz_data, psi_data)
    
    print(f"\n📊 AEO Total Score: {aeo_scores.total}/100 (expected: low)")
    print(f"📍 GEO Total Score: {geo_scores.total}/100 (expected: low)")
    print(f"⚠️  Weaknesses: {len(weaknesses)} (expected: high)")
    
    for weak in weaknesses:
        print(f"  [{weak.impact.upper()}] {weak.title}")


if __name__ == "__main__":
    try:
        test_rules_loading()
        test_scoring_computation()
        test_missing_data_scenario()
        print("\n" + "="*60)
        print("✅ All tests completed successfully!")
        print("="*60)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
