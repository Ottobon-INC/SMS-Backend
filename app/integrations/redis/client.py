from app.core.config.settings import settings


def get_redis_url() -> str:
    return settings.redis_url
