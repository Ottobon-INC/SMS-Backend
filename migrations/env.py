from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.model_registry import import_foundation_models
from app.shared.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import_foundation_models()
target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    """Restrict Alembic comparison to public sms_* objects."""

    if type_ == "table":
        return name.startswith("sms_")
    if hasattr(object_, "table") and object_.table is not None:
        return object_.table.name.startswith("sms_")
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
