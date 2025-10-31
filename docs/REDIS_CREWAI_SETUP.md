# Redis & CrewAI Setup Guide

Complete guide to enable Redis caching and CrewAI with Ollama for your AEO/GEO scanning project.

---

## 🎯 Overview

This project uses three key services:

1. **Lighthouse (PageSpeed Insights)** - Web performance & SEO metrics ✅ Working
2. **KeyBERT** - Keyphrase extraction ✅ Working (Redis now configured)
3. **CrewAI + Ollama** - AI-powered insights ⚠️ Requires manual setup

---

## 🔴 PART 1: Redis Caching (COMPLETED)

### What Changed

- ✅ Added Redis service to `docker-compose.yml`
- ✅ Configured `REDIS_URL=redis://redis:6379/0` in `.env`
- ✅ Redis persistence enabled (data survives restarts)
- ✅ Memory limit: 512MB with LRU eviction policy

### Redis Configuration

```yaml
# In docker-compose.yml
redis:
  image: redis:7-alpine
  command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
  volumes:
    - redis-data:/data
```

### How KeyBERT Uses Redis

```python
# Automatically caches extracted keyphrases for 12 hours
# Cache key: kp:{sha1(text)}:{top_n}:{text_limit}
# Benefits:
# - Faster response for repeated URLs
# - Reduced CPU/GPU load
# - Lower KeyBERT processing time
```

### Verify Redis is Working

```bash
# Check Redis is running
docker compose ps redis

# Test Redis connection from backend
docker compose exec backend python -c "
import redis
r = redis.Redis.from_url('redis://redis:6379/0')
print('Redis ping:', r.ping())
"

# Check cache stats
docker compose exec redis redis-cli INFO stats
```

---

## 🤖 PART 2: Enable CrewAI with Ollama

### Prerequisites

- **8GB+ RAM** (16GB recommended for llama3.2:3b)
- **10GB+ disk space** for model storage
- **Windows, macOS, or Linux**

---

### Step 1: Install Ollama

#### Windows/Mac:

1. Download from: https://ollama.com/download
2. Run installer
3. Verify: `ollama --version`

#### Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

---

### Step 2: Pull the Model

```bash
# Pull llama3.2 3B model (~2GB download)
ollama pull llama3.2:3b

# Verify model is available
ollama list
```

**Expected output:**

```
NAME              ID              SIZE      MODIFIED
llama3.2:3b       abc123def456    1.9GB     2 minutes ago
```

---

### Step 3: Start Ollama Server

```bash
# Start Ollama (runs on http://localhost:11434)
ollama serve
```

**Keep this terminal open!** Or run as a service:

#### Windows (Service):

```powershell
# Ollama auto-starts as Windows service after installation
# Check status:
Get-Service Ollama
```

#### Linux (Systemd):

```bash
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama
```

---

### Step 4: Test Ollama Connection

```bash
# Test from command line
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2:3b",
  "prompt": "Why is the sky blue?",
  "stream": false
}'

# Should return JSON with generated text
```

---

### Step 5: Enable CrewAI in Your Project

Edit `.env`:

```bash
# Change this line:
CREW_AI_ENABLED=false

# To:
CREW_AI_ENABLED=true
```

Restart backend:

```bash
docker compose restart backend
```

---

### Step 6: Verify CrewAI is Working

```bash
# Check backend logs for AI initialization
docker compose logs backend | grep -i "crew\|llm\|ollama"

# Test AI insights generation
docker compose exec backend python -c "
from app.services.crewai_reasoner import generate_recommendations

scan = {'url': 'https://example.com', 'title': 'Test'}
lighthouse = {'performance': 0.85, 'seo': 0.90}

result = generate_recommendations(scan, lighthouse, timeout_seconds=30)
print('AI Response:', result.get('visibility_score_explainer', 'No response')[:100])
"
```

**Expected output:**

```
AI Response: Based on the performance score of 0.85 and SEO score of 0.90, this website shows strong...
```

---

## ⚙️ PART 3: Optimized Configuration

### Development Settings (.env)

```bash
# PageSpeed Insights
PSI_API_KEY=your_api_key_here
PSI_CACHE_TTL_SECONDS=3600        # 1 hour (faster iteration)
SCAN_MAX_CONCURRENCY=2             # Conservative for dev
SCAN_JOB_TTL_SECONDS=120

# KeyBERT
KEYPHRASES_ENABLED=true
KEYPHRASES_TOP_N=5                 # Fewer for faster dev
KEYPHRASES_TEXT_LIMIT=2000         # Smaller text chunks
KEYPHRASES_TIMEOUT_MS=1500
KEYPHRASES_CACHE_TTL_SECONDS=3600  # 1 hour

# Redis
REDIS_URL=redis://redis:6379/0

# CrewAI
CREW_AI_ENABLED=true
LLM_TIMEOUT_SECONDS=20             # Shorter for dev
LLM_TEMPERATURE=0.3                # More creative
LLM_MAX_TOKENS=1500
MODEL=ollama/llama3.2:3b
OLLAMA_HOST=http://host.docker.internal:11434
```

### Production Settings (.env)

```bash
# PageSpeed Insights
PSI_API_KEY=your_production_api_key
PSI_CACHE_TTL_SECONDS=43200        # 12 hours (reduce API calls)
SCAN_MAX_CONCURRENCY=5             # Higher throughput
SCAN_JOB_TTL_SECONDS=300           # Longer timeout

# KeyBERT
KEYPHRASES_ENABLED=true
KEYPHRASES_TOP_N=8                 # More comprehensive
KEYPHRASES_TEXT_LIMIT=3000         # Larger text analysis
KEYPHRASES_TIMEOUT_MS=3000         # Allow more time
KEYPHRASES_CACHE_TTL_SECONDS=86400 # 24 hours

# Redis
REDIS_URL=redis://redis:6379/0

# CrewAI
CREW_AI_ENABLED=true
LLM_TIMEOUT_SECONDS=30             # More generous
LLM_TEMPERATURE=0.2                # More deterministic
LLM_MAX_TOKENS=2000
MODEL=ollama/llama3.2:3b           # Or llama3:8b for better quality
OLLAMA_HOST=http://host.docker.internal:11434
```

### High-Performance Settings (16GB+ RAM)

```bash
# Use larger model for better insights
MODEL=ollama/llama3:8b             # ~4.7GB model
# or
MODEL=ollama/llama3:70b            # ~40GB model (requires GPU)

# Increase concurrency
SCAN_MAX_CONCURRENCY=10
KEYPHRASES_TOP_N=12
LLM_TIMEOUT_SECONDS=45
```

---

## 🧪 Testing All Services

### Complete System Test

Create `test_all_services.py`:

```python
"""Test all AEO/GEO services."""
import os
import sys

def test_redis():
    print("\n🔴 Testing Redis...")
    try:
        import redis
        r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        r.ping()
        r.set("test_key", "test_value", ex=10)
        assert r.get("test_key") == b"test_value"
        print("✅ Redis: WORKING")
        return True
    except Exception as e:
        print(f"❌ Redis: FAILED - {e}")
        return False

def test_keybert():
    print("\n🔍 Testing KeyBERT with Redis caching...")
    try:
        from app.services.keyphrases import extract_keyphrases
        text = "SEO optimization and local search visibility are critical for business"

        # First call (no cache)
        kp1 = extract_keyphrases(text, top_n=5, cache_key="test123")
        print(f"   Keyphrases: {kp1}")

        # Second call (from cache)
        kp2 = extract_keyphrases(text, top_n=5, cache_key="test123")
        assert kp1 == kp2

        print("✅ KeyBERT + Redis: WORKING")
        return True
    except Exception as e:
        print(f"❌ KeyBERT: FAILED - {e}")
        return False

def test_psi():
    print("\n🚨 Testing PageSpeed Insights...")
    try:
        from app.services.psi_scan import run_psi_scan
        result = run_psi_scan("https://example.com", strategy="mobile")
        lh = result.get("lighthouse", {})
        print(f"   Performance: {lh.get('performance')}")
        print(f"   SEO: {lh.get('seo')}")
        print("✅ Lighthouse/PSI: WORKING")
        return True
    except Exception as e:
        print(f"❌ Lighthouse: FAILED - {e}")
        return False

def test_crewai():
    print("\n🤖 Testing CrewAI + Ollama...")

    crew_enabled = os.getenv("CREW_AI_ENABLED", "false").lower() == "true"
    if not crew_enabled:
        print("⚠️  CrewAI: DISABLED (set CREW_AI_ENABLED=true)")
        return None

    try:
        from app.services.crewai_reasoner import generate_recommendations

        scan = {"url": "https://example.com", "title": "Test Site"}
        lighthouse = {"performance": 0.85, "seo": 0.90, "accessibility": 0.88}

        result = generate_recommendations(scan, lighthouse, timeout_seconds=30)
        explainer = result.get("visibility_score_explainer", "")

        print(f"   Explainer: {explainer[:100]}...")
        print(f"   Findings: {len(result.get('top_findings', []))}")
        print(f"   Recommendations: {len(result.get('recommendations', []))}")
        print("✅ CrewAI + Ollama: WORKING")
        return True
    except Exception as e:
        print(f"❌ CrewAI: FAILED - {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("🧪 TESTING ALL AEO/GEO SERVICES")
    print("="*60)

    results = {
        "Redis": test_redis(),
        "KeyBERT": test_keybert(),
        "Lighthouse": test_psi(),
        "CrewAI": test_crewai()
    }

    print("\n" + "="*60)
    print("📊 RESULTS")
    print("="*60)
    for service, status in results.items():
        if status is True:
            print(f"✅ {service}: WORKING")
        elif status is False:
            print(f"❌ {service}: FAILED")
        else:
            print(f"⚠️  {service}: DISABLED")
    print("="*60)
```

Run test:

```bash
docker compose exec backend python test_all_services.py
```

---

## 🔧 Troubleshooting

### Redis Issues

**Problem:** Backend can't connect to Redis

```bash
# Check Redis is running
docker compose ps redis

# Check logs
docker compose logs redis

# Test connection manually
docker compose exec redis redis-cli ping
# Should return: PONG
```

**Problem:** Redis memory issues

```bash
# Check memory usage
docker compose exec redis redis-cli INFO memory

# Increase maxmemory in docker-compose.yml:
command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
```

---

### CrewAI/Ollama Issues

**Problem:** "Connection refused" to Ollama

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check host.docker.internal works from container
docker compose exec backend curl http://host.docker.internal:11434/api/tags
```

**Fix:** If host.docker.internal doesn't work:

```bash
# Option 1: Use host network (Linux only)
# In docker-compose.yml backend section:
network_mode: "host"

# Option 2: Use host IP address
# Find your IP:
ip addr show  # Linux
ipconfig      # Windows

# Update .env:
OLLAMA_HOST=http://192.168.1.100:11434  # Use your IP
```

**Problem:** Model generation too slow

```bash
# Use smaller model
MODEL=ollama/llama3.2:1b  # ~900MB, faster but less accurate

# Or increase timeout
LLM_TIMEOUT_SECONDS=60
```

**Problem:** Ollama model not found

```bash
# List available models
ollama list

# Pull the exact model specified in .env
ollama pull llama3.2:3b

# Check model name matches .env
MODEL=ollama/llama3.2:3b  # Must match exactly
```

---

### Performance Issues

**Problem:** Scans timing out

```bash
# Increase timeouts
SCAN_JOB_TTL_SECONDS=300
KEYPHRASES_TIMEOUT_MS=5000
LLM_TIMEOUT_SECONDS=60

# Reduce concurrency
SCAN_MAX_CONCURRENCY=2
```

**Problem:** High memory usage

```bash
# Limit Redis memory
# In docker-compose.yml:
command: redis-server --maxmemory 256mb

# Use smaller KeyBERT model
KEYBERT_MODEL=all-MiniLM-L6-v2  # Default, ~90MB

# Reduce text processing
KEYPHRASES_TEXT_LIMIT=1500
KEYPHRASES_TOP_N=5
```

---

## 📊 Monitoring

### Redis Stats

```bash
# Real-time stats
docker compose exec redis redis-cli --stat

# Cache hit rate
docker compose exec redis redis-cli INFO stats | grep keyspace
```

### Service Health

```bash
# Check all services
docker compose ps

# Backend health
curl http://localhost:8000/api/v1/utils/health-check/

# View logs
docker compose logs -f backend redis
```

---

## 🚀 Quick Start Commands

```bash
# 1. Start all services (Redis included)
docker compose up -d

# 2. Install Ollama (if enabling CrewAI)
# Download from https://ollama.com/download

# 3. Pull model
ollama pull llama3.2:3b

# 4. Enable CrewAI in .env
# CREW_AI_ENABLED=true

# 5. Restart backend
docker compose restart backend

# 6. Test everything
docker compose exec backend python test_all_services.py

# 7. Access application
# Frontend: http://localhost:5174
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

---

## 📈 Production Checklist

- [ ] Redis persistent volume configured
- [ ] PSI API key quota verified (25,000/day free)
- [ ] Ollama running as system service
- [ ] Model downloaded and verified
- [ ] All environment variables set correctly
- [ ] Firewall allows Ollama port (11434)
- [ ] Health checks passing
- [ ] Monitoring configured (Redis stats, API latency)
- [ ] Backup strategy for Redis data
- [ ] Load testing completed

---

## 🎓 Additional Resources

- **Ollama Models**: https://ollama.com/library
- **Redis Commands**: https://redis.io/commands
- **KeyBERT Docs**: https://maartengr.github.io/KeyBERT/
- **PageSpeed API**: https://developers.google.com/speed/docs/insights/v5/get-started
- **CrewAI**: https://docs.crewai.com/

---

**Last Updated:** October 27, 2025
**Version:** 1.0.0
