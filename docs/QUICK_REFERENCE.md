# ⚡ Quick Reference: Redis + CrewAI

## 🔴 Redis (ENABLED)

**Status:** ✅ Configured and ready

```bash
# Start services
docker compose up -d

# Verify Redis
docker compose exec redis redis-cli ping
# Expected: PONG

# Check backend can connect
docker compose exec backend python -c "import redis; r=redis.Redis.from_url('redis://redis:6379/0'); print('✅ Connected' if r.ping() else '❌ Failed')"
```

**Configuration:**

- URL: `redis://redis:6379/0`
- Memory: 512MB (auto-evicts old cache)
- Persistence: Yes (survives restarts)
- Used by: KeyBERT caching

---

## 🤖 CrewAI (DISABLED - Enable Instructions Below)

**Current Status:** ⚠️ Disabled (`CREW_AI_ENABLED=false`)

### Enable in 4 Steps:

#### 1. Install Ollama

```bash
# Windows/Mac: Download from https://ollama.com/download
# Linux:
curl -fsSL https://ollama.com/install.sh | sh
```

#### 2. Pull Model

```bash
ollama pull llama3.2:3b
# Wait ~2 minutes for 1.9GB download
```

#### 3. Start Ollama

```bash
# Start server (keep running)
ollama serve
# Or: Use system service (Windows auto-starts after install)
```

#### 4. Enable in .env

```bash
# Edit .env:
CREW_AI_ENABLED=true

# Restart backend:
docker compose restart backend
```

### Verify Working

```bash
# Test Ollama locally
curl http://localhost:11434/api/tags

# Test from Docker container
docker compose exec backend curl http://host.docker.internal:11434/api/tags

# Test AI generation
docker compose exec backend python -c "
from app.services.crewai_reasoner import generate_recommendations
result = generate_recommendations({'url': 'test'}, {'performance': 0.8}, timeout_seconds=20)
print('✅ AI Working:', 'visibility' in result.get('visibility_score_explainer', ''))
"
```

---

## ⚙️ Configuration Quick Reference

### Current Settings (.env)

```bash
# Redis
REDIS_URL=redis://redis:6379/0              # ✅ Active

# KeyBERT + Redis
KEYPHRASES_ENABLED=true                      # ✅ Active
KEYPHRASES_TOP_N=8                           # Number of keyphrases
KEYPHRASES_TEXT_LIMIT=3000                   # Max words to analyze
KEYPHRASES_TIMEOUT_MS=2000                   # 2 second timeout
KEYPHRASES_CACHE_TTL_SECONDS=43200          # 12 hour cache

# CrewAI (change to true to enable)
CREW_AI_ENABLED=false                        # ⚠️ DISABLED
LLM_TIMEOUT_SECONDS=30
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=2000
MODEL=ollama/llama3.2:3b
OLLAMA_HOST=http://host.docker.internal:11434

# PageSpeed Insights
PSI_API_KEY=your_key_here                    # ✅ Set
PSI_CACHE_TTL_SECONDS=43200                 # 12 hour cache
SCAN_MAX_CONCURRENCY=3
SCAN_JOB_TTL_SECONDS=120
```

---

## 🧪 One-Line Test Commands

```bash
# Test Redis
docker compose exec redis redis-cli PING

# Test KeyBERT (should use Redis cache)
docker compose exec backend python -c "from app.services.keyphrases import extract_keyphrases; print(extract_keyphrases('SEO optimization'))"

# Test PageSpeed Insights
docker compose exec backend python -c "from app.services.psi_scan import run_psi_scan; print('PSI:', run_psi_scan('https://example.com')['lighthouse']['performance'])"

# Test CrewAI (only if enabled)
docker compose exec backend python -c "from app.services.crewai_reasoner import generate_recommendations; print(generate_recommendations({'url': 'test'}, {'performance': 0.85})['visibility_score_explainer'][:50])"
```

---

## 🔧 Common Issues

| Problem                    | Quick Fix                                |
| -------------------------- | ---------------------------------------- |
| Redis connection refused   | `docker compose restart redis`           |
| Ollama not found           | Install from https://ollama.com/download |
| Model not found            | `ollama pull llama3.2:3b`                |
| host.docker.internal fails | Use `OLLAMA_HOST=http://YOUR_IP:11434`   |
| AI timeout                 | Increase `LLM_TIMEOUT_SECONDS=60`        |
| High memory                | Use `MODEL=ollama/llama3.2:1b` (smaller) |

---

## 📊 Service Status Check

```bash
# All services
docker compose ps

# Logs
docker compose logs -f backend redis

# Redis info
docker compose exec redis redis-cli INFO stats

# Cache hit rate
docker compose exec redis redis-cli INFO stats | grep keyspace_hits
```

---

## 🎯 Performance Tuning

### For Speed (Dev Environment)

```bash
SCAN_MAX_CONCURRENCY=2
KEYPHRASES_TOP_N=5
KEYPHRASES_TEXT_LIMIT=1500
LLM_TIMEOUT_SECONDS=15
MODEL=ollama/llama3.2:1b              # Faster, less accurate
```

### For Quality (Production)

```bash
SCAN_MAX_CONCURRENCY=5
KEYPHRASES_TOP_N=10
KEYPHRASES_TEXT_LIMIT=5000
LLM_TIMEOUT_SECONDS=45
MODEL=ollama/llama3:8b                # Slower, more accurate
```

---

## 🚀 Start Everything

```bash
# 1. Start Docker services (Redis + Backend + DB)
docker compose up -d

# 2. If enabling CrewAI:
#    a. Install Ollama
#    b. Run: ollama pull llama3.2:3b
#    c. Run: ollama serve (or service auto-starts)
#    d. Edit .env: CREW_AI_ENABLED=true
#    e. Run: docker compose restart backend

# 3. Access app
#    Frontend: http://localhost:5174
#    Backend: http://localhost:8000
#    API Docs: http://localhost:8000/docs

# 4. Test everything
docker compose exec backend python test_all_services.py
```

---

**Need detailed setup?** See `docs/REDIS_CREWAI_SETUP.md`
