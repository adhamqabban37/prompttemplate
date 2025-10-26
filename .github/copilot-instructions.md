# Copilot instructions for this repository

This repo uses the Full Stack FastAPI Template. Do not change the project structure. Follow the project spec at docs/project-spec.md.

## What agents must know
- Tech stack is fixed: backend/ (FastAPI, SQLModel, Alembic, uv), frontend/ (React + Vite), Docker Compose services (db, backend, proxy, adminer, etc.).
- Use docker compose for backend/db/proxy; run Vite locally for HMR.
- Stripe will be used for payments (see Env vars).

## Scope for Xenlixai (MVP)
- URL analysis preview (summary + SEO + geo/local SEO cues).
- Stripe Checkout to upgrade to premium.
- Premium dashboard with richer insights.

## Conventions
- Backend code under backend/app/...; add new routers in backend/app/api/routes/ and include in api/main.py.
- DB models with SQLModel; new migrations via Alembic.
- Frontend routes under frontend/src/routes/; components in frontend/src/components/.
- OpenAPI client generation is configured (frontend/openapi-ts.config.ts).

## Commands
- Backend/db/proxy: docker compose up -d --build (compose.override enables dev reload)
- Frontend HMR: cd frontend && npm install && npm run dev (port 5173)
- Logs: docker compose logs -f [service]

## Env
- Root .env used by compose. Add Stripe keys: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID. Set FRONTEND_HOST/BACKEND_PUBLIC_URL accordingly.

## Guardrails
- Do NOT move/rename top-level folders or docker files.
- Prefer minimal, localized changes; update docs/project-spec.md if scope evolves.
- Before adding libraries, check if the template already covers the need.

See docs/project-spec.md for the detailed product contract; treat it as the source of truth.


> Current focus: build core backend routes step-by-step; avoid UI/styling changes unless asked. See docs/project-spec.md (Update 2025-10-25).
