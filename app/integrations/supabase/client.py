from app.core.config.settings import settings


def get_supabase_url() -> str:
    return settings.supabase_url
