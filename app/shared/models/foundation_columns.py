"""Column helpers for database-first foundation model mappings."""

# mypy: ignore-errors

from sqlalchemy import Boolean, Date, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID, VARCHAR
from sqlalchemy.sql.schema import Column


def uuid_pk(name: str = "id") -> Column[object]:
    return Column(
        name,
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


def uuid_col(name: str, *, nullable: bool = True, default: str | None = None) -> Column[object]:
    return Column(
        name,
        UUID(as_uuid=True),
        nullable=nullable,
        server_default=text(default) if default else None,
    )


def text_col(name: str, *, nullable: bool = True, default: str | None = None) -> Column[object]:
    return Column(name, Text, nullable=nullable, server_default=text(default) if default else None)


def varchar(
    name: str,
    length: int,
    *,
    nullable: bool = True,
    default: str | None = None,
) -> Column[object]:
    return Column(
        name,
        VARCHAR(length),
        nullable=nullable,
        server_default=text(default) if default else None,
    )


def jsonb(name: str, *, nullable: bool = False, default: str = "'{}'::jsonb") -> Column[object]:
    return Column(name, JSONB, nullable=nullable, server_default=text(default) if default else None)


def timestamp(name: str, *, nullable: bool = True, default_now: bool = False) -> Column[object]:
    return Column(
        name,
        DateTime(timezone=False),
        nullable=nullable,
        server_default=text("now()") if default_now else None,
    )


def date_col(name: str, *, nullable: bool = True) -> Column[object]:
    return Column(name, Date, nullable=nullable)


def bool_col(name: str, *, nullable: bool = False, default: str | None = None) -> Column[object]:
    return Column(
        name,
        Boolean,
        nullable=nullable,
        server_default=text(default) if default else None,
    )


def int_col(name: str, *, nullable: bool = True, default: str | None = None) -> Column[object]:
    return Column(
        name,
        Integer,
        nullable=nullable,
        server_default=text(default) if default else None,
    )
