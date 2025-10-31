FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface/transformers \
    SENTENCE_TRANSFORMERS_HOME=/root/.cache/sentence-transformers \
    PYTHONPATH=/app

WORKDIR /app/

# System deps for lxml and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    curl \
    ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install pinned heavy deps in a separate layer for better caching
RUN pip install --no-cache-dir \
    torch==2.3.1 \
    sentence-transformers==2.7.0 \
    keybert==0.8.4 \
    redis==5.0.7

# Pre-warm sentence-transformers model so first request is fast
RUN python - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer('all-MiniLM-L6-v2')
print('Model prewarmed')
PY

# Copy project files
COPY ./pyproject.toml ./uv.lock ./alembic.ini /app/
COPY ./scripts /app/scripts
COPY ./app /app/app
COPY ./config /app/config
COPY ./tests /app/tests

# Install uv to sync remaining project deps from pyproject
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/
ENV PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Sync project dependencies (cached)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Ensure lightweight runtime deps not present in the frozen lock are available
RUN uv pip install --python /app/.venv/bin/python \
    'jmespath>=1.0.1,<2.0.0' \
    'beautifulsoup4>=4.12.0,<5.0.0' \
    'trafilatura>=1.6.0,<2.0.0' \
    'extruct>=0.16.0,<1.0.0' \
    'anyio>=3.0.0,<5.0.0'

# Default command
CMD ["fastapi", "run", "--host", "0.0.0.0", "--workers", "4", "app/main.py"]
