from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.routes.auth import router as auth_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.audits import router as audits_router
from app.api.routes.documents import router as documents_router
from app.api.routes.regulatory import (
    regulatory_router,
    audit_requirements_router,
)
from app.api.routes.threats import threats_router
from app.api.routes.defence import defence_router
from app.config import settings
from app.database.connection import get_db, check_db_health

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("compliance_sentinel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Compliance Sentinel API starting up...")
    health = check_db_health()
    if health.get("status") == "healthy":
        logger.info(f"Connected to YugabyteDB YSQL: {health.get('database')} (user: {health.get('user')})")
    else:
        logger.warning(f"Initial database check reported: {health.get('error')}")
    yield
    logger.info("Compliance Sentinel API shutting down...")


app = FastAPI(
    title="Compliance Sentinel API",
    description="Multi-tenant AI-powered compliance auditing SaaS engine with YugabyteDB backend",
    version="4.0.0",
    lifespan=lifespan,
)

# CORS configuration
origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(organizations_router)
app.include_router(audits_router)
app.include_router(documents_router)
app.include_router(regulatory_router)
app.include_router(audit_requirements_router)
app.include_router(threats_router)
app.include_router(defence_router)


@app.get("/health", status_code=status.HTTP_200_OK, tags=["System"])
@app.get("/api/health", status_code=status.HTTP_200_OK, tags=["System"])
def health_check():
    """Health endpoint that verifies service readiness and database connectivity."""
    db_health = check_db_health()
    is_healthy = db_health.get("status") == "healthy"
    return {
        "status": "healthy" if is_healthy else "degraded",
        "service": "Compliance Sentinel API",
        "version": "4.0.0",
        "environment": settings.FASTAPI_ENV,
        "database": db_health,
    }


@app.get("/", tags=["System"])
def root():
    return {
        "name": "Compliance Sentinel API",
        "version": "4.0.0",
        "docs_url": "/docs",
        "health_url": "/api/health",
    }
