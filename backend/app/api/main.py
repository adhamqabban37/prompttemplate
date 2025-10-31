from fastapi import APIRouter
from fastapi.routing import APIRoute
from app.api.routes import items, login, private, users, utils, analyze, scan, rules, health, warmup, orchestrator, analyze_url, scan_jobs, payments, billing
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(analyze.router)
api_router.include_router(scan.router)
api_router.include_router(rules.router)
api_router.include_router(health.router)
api_router.include_router(warmup.router)
api_router.include_router(items.router)
api_router.include_router(orchestrator.router)
api_router.include_router(analyze_url.router)
api_router.include_router(scan_jobs.router)
api_router.include_router(payments.router)
api_router.include_router(billing.router)
