from sqlmodel import Session, create_engine, select
import time
import sys
from typing import Tuple

from app import crud
from app.core.config import settings
from app.models import User, UserCreate

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"Creating engine with URI: {settings.SQLALCHEMY_DATABASE_URI}")
logger.info(f"POSTGRES_USER from settings: {settings.POSTGRES_USER}")

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def check_db_connection(max_retries: int = 5, initial_delay: float = 0.5) -> Tuple[bool, str]:
    """
    Check database connectivity with exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of connection attempts (default: 5)
        initial_delay: Initial delay in seconds before first retry (default: 0.5s)
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    delay = initial_delay
    max_delay = 10.0  # Cap delay at 10 seconds
    
    # Build connection string for logging (mask password)
    conn_str = f"postgresql+psycopg://{settings.POSTGRES_USER}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"🔍 Checking database connection (attempt {attempt}/{max_retries})...")
            logger.info(f"   Trying to connect: {conn_str}")
            
            # Attempt to connect and execute a simple query
            with engine.connect() as connection:
                result = connection.execute(select(1))
                result.close()  # Ensure connection is released
                logger.info("✅ Database connection successful!")
                return True, "connected"
                
        except Exception as e:
            error_msg = str(e)
            # Log at warning level for retries, error level for final failure
            log_level = logger.warning if attempt < max_retries else logger.error
            log_level(f"❌ Database connection attempt {attempt}/{max_retries} failed: {type(e).__name__}")
            
            if attempt < max_retries:
                actual_delay = min(delay, max_delay)
                logger.info(f"⏳ Retrying in {actual_delay:.1f}s...")
                time.sleep(actual_delay)
                delay *= 2  # Exponential backoff
            else:
                logger.error(f"❌ Database unreachable after {max_retries} attempts")
                return False, f"unreachable: {error_msg}"
    
    return False, "unreachable"


def check_db_connection_sync() -> Tuple[bool, str]:
    """
    Synchronous version of database health check for use in startup handlers.
    Returns (is_healthy, status_message)
    """
    try:
        with engine.connect() as connection:
            connection.execute(select(1))
            return True, "connected"
    except Exception as e:
        return False, f"unreachable: {str(e)}"


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
