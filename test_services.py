"""Test script to verify Lighthouse (PSI), CrewAI, and KeyBERT are working."""
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

def test_keybert():
    """Test KeyBERT keyphrase extraction."""
    print("\n🔍 Testing KeyBERT...")
    try:
        from app.services.keyphrases import extract_keyphrases
        
        text = "Search engine optimization and local SEO are critical for business visibility online."
        keyphrases = extract_keyphrases(text, top_n=5, timeout_ms=5000)
        
        print(f"✅ KeyBERT is working!")
        print(f"   Input: {text[:60]}...")
        print(f"   Keyphrases extracted: {keyphrases}")
        return True
    except Exception as e:
        print(f"❌ KeyBERT failed: {e}")
        return False


def test_psi_lighthouse():
    """Test PageSpeed Insights (Lighthouse) API."""
    print("\n🚨 Testing Lighthouse (PageSpeed Insights)...")
    try:
        from app.services.psi_scan import run_psi_scan
        
        # Test with a simple URL
        result = run_psi_scan("https://example.com", strategy="mobile")
        
        if result and "lighthouse" in result:
            print(f"✅ Lighthouse/PSI is working!")
            lh = result["lighthouse"]
            print(f"   Performance: {lh.get('performance', 'N/A')}")
            print(f"   SEO: {lh.get('seo', 'N/A')}")
            print(f"   Accessibility: {lh.get('accessibility', 'N/A')}")
            return True
        else:
            print(f"❌ Lighthouse/PSI returned unexpected result: {result}")
            return False
    except Exception as e:
        print(f"❌ Lighthouse/PSI failed: {e}")
        return False


def test_crewai():
    """Test CrewAI reasoning."""
    print("\n🤖 Testing CrewAI...")
    
    # Check if enabled
    crew_ai_enabled = os.getenv("CREW_AI_ENABLED", "false").lower() == "true"
    
    if not crew_ai_enabled:
        print(f"⚠️  CrewAI is DISABLED (CREW_AI_ENABLED={os.getenv('CREW_AI_ENABLED', 'false')})")
        print("   To enable: Set CREW_AI_ENABLED=true in .env")
        print("   Make sure Ollama is running with the model specified in .env")
        return None  # Not a failure, just disabled
    
    try:
        from app.services.crewai_reasoner import generate_recommendations
        
        # Mock scan data
        scan_data = {
            "url": "https://example.com",
            "title": "Example Domain",
            "description": "Example website for testing"
        }
        
        lighthouse_data = {
            "performance": 0.85,
            "seo": 0.90,
            "accessibility": 0.88
        }
        
        result = generate_recommendations(scan_data, lighthouse_data, timeout_seconds=10)
        
        if result and "visibility_score_explainer" in result:
            print(f"✅ CrewAI is working!")
            print(f"   Explainer: {result['visibility_score_explainer'][:100]}...")
            print(f"   Top findings: {len(result.get('top_findings', []))} items")
            print(f"   Recommendations: {len(result.get('recommendations', []))} items")
            return True
        else:
            print(f"❌ CrewAI returned unexpected result: {result}")
            return False
    except Exception as e:
        print(f"❌ CrewAI failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 Testing XenlixAI Services")
    print("=" * 60)
    
    results = {
        "KeyBERT": test_keybert(),
        "Lighthouse/PSI": test_psi_lighthouse(),
        "CrewAI": test_crewai()
    }
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    
    for service, result in results.items():
        if result is True:
            print(f"✅ {service}: WORKING")
        elif result is False:
            print(f"❌ {service}: FAILED")
        else:
            print(f"⚠️  {service}: DISABLED")
    
    print("=" * 60)
    
    # Return exit code
    failed = [k for k, v in results.items() if v is False]
    if failed:
        print(f"\n❌ {len(failed)} service(s) failed: {', '.join(failed)}")
        return 1
    else:
        print("\n✅ All enabled services are working!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
