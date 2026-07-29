from fastapi import FastAPI

from app.api.health.router import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config.settings import settings
from app.core.logging.setup import configure_logging
from app.core.middleware.correlation_id import correlation_id_middleware

configure_logging()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.middleware("http")(correlation_id_middleware)
app.include_router(health_router)
app.include_router(v1_router)
