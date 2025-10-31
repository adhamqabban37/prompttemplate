import sentry_sdk
from fastapi import FastAPI
import logging
import sys
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from typing import Optional

from app.api.main import api_router
from app.core.config import settings


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate a stable unique operationId for OpenAPI.

    Some programmatically added routes (like /metrics) may have no tags; in that
    case fall back to the route name to avoid IndexError.
    """
    if getattr(route, "tags", None):
        return f"{route.tags[0]}-{route.name}"
    return route.name


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

# Prometheus metrics instrumentation (fully guarded)
instrumentator: Optional[object] = None
try:
    from prometheus_fastapi_instrumentator import Instrumentator  # type: ignore

    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=False,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )
    instrumentator.instrument(app)
except Exception as e:  # ImportError or any instrumentation failure
    # Never block app startup due to metrics issues
    logging.getLogger(__name__).warning(f"Prometheus metrics disabled: {e}")

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


logger = logging.getLogger(__name__)


@app.on_event("startup")
async def _check_database_connection() -> None:
    """
    Verify database connectivity on startup with retry logic.
    
    In development/local mode (unless FORCE_STRICT_STARTUP=true):
    - Retries connection up to 10 times with longer delays
    - Logs warnings but continues if database is unreachable
    - Allows the application to start even if DB is still initializing
    
    In production/staging mode or FORCE_STRICT_STARTUP=true:
    - Strict validation with 5 retries
    - Exits with sys.exit(1) if database is unreachable
    """
    from app.core.db import check_db_connection
    
    logger.info("=" * 60)
    logger.info("🚀 Starting database health check...")
    logger.info(f"   Environment: {settings.ENVIRONMENT}")
    logger.info(f"   Database: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    logger.info(f"   User: {settings.POSTGRES_USER}")
    logger.info(f"   Connection: postgresql+psycopg://{settings.POSTGRES_USER}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    logger.info(f"   Strict startup: {settings.FORCE_STRICT_STARTUP}")
    logger.info("=" * 60)
    
    # Different retry strategies based on environment
    # Use strict mode in production OR if explicitly forced
    is_strict_mode = (settings.ENVIRONMENT in ("production", "staging")) or settings.FORCE_STRICT_STARTUP
    is_development = not is_strict_mode
    
    max_retries = 10 if is_development else 5
    initial_delay = 1.0 if is_development else 0.5
    
    logger.info(f"🔧 Mode: {'STRICT (will exit on failure)' if is_strict_mode else 'RESILIENT (will continue on failure)'}")
    logger.info(f"🔧 Retries: {max_retries}, Initial delay: {initial_delay}s")
    
    is_healthy, status_msg = check_db_connection(
        max_retries=max_retries,
        initial_delay=initial_delay
    )
    
    if not is_healthy:
        if is_development:
            # In development, log error but allow startup to continue
            logger.error("=" * 60)
            logger.error("⚠️  WARNING: Database connection failed!")
            logger.error(f"   Status: {status_msg}")
            logger.error("   Development mode: Application will start anyway")
            logger.error("   Database-dependent features may not work")
            logger.error("   /api/v1/utils/health-check/ will return 503")
            logger.error("=" * 60)
        else:
            # In production or strict mode, exit immediately
            logger.critical("=" * 60)
            logger.critical("❌ FATAL: Database connection failed!")
            logger.critical(f"   Status: {status_msg}")
            logger.critical("   The application cannot start without a database.")
            logger.critical("=" * 60)
            sys.exit(1)
    else:
        logger.info("=" * 60)
        logger.info("✅ Database ready - application starting normally")
        logger.info("=" * 60)


@app.on_event("startup")
async def _log_llm_config_on_startup() -> None:
    """Eagerly initialize LLM once to log model/base_url configuration."""
    try:
        from app.services.llm_factory import get_llm

        # Instantiate (no network call) just to emit config logs
        get_llm()
        logger.info("LLM configured and ready (see previous log for model/base_url)")
    except Exception as e:
        logger.warning(f"LLM not initialized at startup: {e}")


@app.on_event("startup")
async def _expose_metrics_endpoint() -> None:
    """Expose Prometheus metrics endpoint and initialize app info."""
    try:
        from app.metrics import initialize_app_info
        
        # Initialize app version and environment
        initialize_app_info(version="0.1.0", environment=settings.ENVIRONMENT)
        
        # Expose metrics endpoint
        instrumentator.expose(app, endpoint="/metrics", include_in_schema=True)
        logger.info("Prometheus metrics available at /metrics")
    except Exception as e:
        logger.warning(f"Failed to expose metrics: {e}")
