import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health.router import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config.settings import settings
from app.core.database.session import check_database_connection, dispose_engine
from app.core.logging.setup import configure_logging
from app.core.middleware.correlation_id import correlation_id_middleware
from app.model_registry import import_foundation_models

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    import_foundation_models()
    try:
        check_database_connection()
    except Exception as exc:
        logger.error("Database startup check failed: %s", exc.__class__.__name__)
        raise
    try:
        yield
    finally:
        dispose_engine()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Access-Assignment-ID", "X-Correlation-ID"],
)
app.middleware("http")(correlation_id_middleware)
app.include_router(health_router)
app.include_router(v1_router)

