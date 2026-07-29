from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Student Management System Backend"
    app_env: str = "local"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://sms_app:change-me@localhost:5432/sms"
    supabase_url: str = "http://localhost:54321"
    redis_url: str = "redis://localhost:6379/0"
    sentry_dsn: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
