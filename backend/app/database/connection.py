import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# Engine configuration with pooling appropriate for YugabyteDB YSQL
database_url = settings.get_database_url()

engine = create_engine(
    database_url,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # Tests connections on checkout to handle closed sockets
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding transactional database sessions."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session rollback triggered by error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def check_db_health() -> dict:
    """Executes a diagnostic query against YugabyteDB to check readiness."""
    try:
        with engine.connect() as conn:
            # Query version and basic connectivity
            res = conn.execute(text("SELECT version(), current_database(), current_user;")).fetchone()
            return {
                "status": "healthy",
                "database": res[1] if res else "unknown",
                "user": res[2] if res else "unknown",
                "version": res[0] if res else "unknown",
            }
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        return {
            "status": "unhealthy",
            "error": str(exc),
        }

