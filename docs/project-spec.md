# Xenlixai – Project Specification

Last updated: 2025-10-25

## Overview
Xenlixai ingests a website URL, analyzes visible content and metadata, produces a concise summary, and surfaces SEO + geo-targeted (local SEO) insights. After a paid upgrade via Stripe Checkout, users access a premium dashboard with deeper recommendations and tools.

## Goals (MVP)
- Input: user submits a public website URL.
- Preview: show site summary, key metadata, top headings/keywords, basic geo/local SEO signals.
- Upgrade: Stripe Checkout (one‑time or subscription – to be finalized) to unlock premium.
- Premium dashboard: richer insights and actions (see below).

## Premium dashboard (initial scope)
- Expanded SEO report (title/description length, headings structure, canonical, robots, sitemap hints).
- Content signals (keyword coverage, readability, internal links overview).
- Local/geo SEO basics (NAP presence, location cues, Google Business Profile hints — no direct API yet).
- Change tracker (re-run analysis and diff results).

## Core flow
1) Anonymous or logged-in user provides URL.
2) Backend fetches and parses the page (respecting robots.txt when applicable), extracts HTML, metadata, headings, links.
3) Summarization + heuristics generate preview (no paid features here).
4) User clicks “Upgrade”; backend creates Stripe Checkout Session and returns URL; frontend redirects.
5) Stripe redirects back to success/cancel; backend verifies via webhook and flags user as premium.
6) Premium dashboard becomes available.

## Integrations
- Stripe (Checkout + Webhooks): payments, premium status.
- Optional later: queue for fetch/analysis at scale (e.g., Celery/RQ) — not in MVP.

## Tech stack anchoring (do not change structure)
- Backend: FastAPI (existing backend/), SQLModel, Alembic, uv, Postgres via docker-compose.
- Frontend: React + Vite (existing frontend/), TanStack Router/Query, Chakra UI.
- Dev: Docker Compose with Traefik, Adminer; local Vite dev for HMR.

## Data model (initial)
- User(id, email, is_premium, stripe_customer_id, created_at)
- Project/Site(id, user_id, url, last_snapshot_id, created_at)
- Snapshot(id, site_id, fetched_at, http_status, meta_json, summary, seo_json)
- Payment(id, user_id, stripe_session_id, status, created_at)

## API (initial endpoints)
- POST /api/v1/analyze { url } -> { summary, seo, snapshot_id }
- POST /api/v1/payments/checkout { plan } -> { checkout_url }
- POST /api/v1/webhooks/stripe (raw body) -> 200
- GET  /api/v1/sites/{id}/snapshots -> list
- GET  /api/v1/me -> user profile incl. premium flag

## Frontend routes
- /            – URL input and preview card
- /upgrade     – triggers Checkout and redirects
- /success     – post‑payment success
- /dashboard   – premium dashboard (protected)

## Env vars (to add)
- STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID (or PRICE_BASIC / PRICE_PRO)
- BACKEND_PUBLIC_URL, FRONTEND_PUBLIC_URL (for return/cancel URLs)

## Non‑functional
- Respect timeouts for fetch (e.g., 10s) and limit content size.
- Sanitize/validate URLs; fetch only http/https.
- Persist minimal PII (email) and payment references; no card data stored.

## Guardrails
- Do NOT restructure the template folders (backend/, frontend/, docker compose files).
- Add new feature code under the existing app/ modules and frontend src/ routes/components.
- All changes must reference this spec. If something isn’t covered, ask before changing structure.

---

## Update (2025-10-25)

Project name: XenlixAI — AEO (Answer Engine Optimization) + GEO (Local SEO)

Vision:
Users enter a website URL → system scans the site → shows an AEO/GEO summary preview (content quality, structured data, E‑E‑A‑T signals, local SEO info). Then users can upgrade via Stripe Checkout to unlock a premium dashboard with detailed analytics, competitor insights, and recommendations.

Tech stack (fixed):
- Backend: FastAPI + SQLModel + Postgres + Docker
- Frontend: React 19 + Vite + Chakra UI + TanStack Router + React Query
- Crawler options: Firecrawl API (optional) OR local extractor (trafilatura + extruct)
- Auth: premium gating (free → paywall → premium dashboard)

Current focus (no UI or styling):
- Build core backend routes step-by-step starting from the template.
- Keep existing structure (backend/, frontend/, docker compose files).

Scope alignment:
- Preview (free): title, headings, meta, AEO/GEO heuristics (basic), high-level E‑E‑A‑T signals.
- Premium: detailed analytics, competitor insights, prioritized recommendations.

Next backend tasks (high-level):
1) Harden /api/v1/analyze: user-agent, robots.txt check (best-effort), timeouts, size caps.
2) Add minimal SQLModel models (Site, Snapshot) and persist snapshots (optional for MVP).
3) Payments: /api/v1/payments/checkout and /api/v1/webhooks/stripe with premium flag.
4) Auth gating in backend responses (expose extra fields only if premium).

Note: Do not change the project structure. All significant changes must reference this spec.
