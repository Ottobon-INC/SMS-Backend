"""Shared SQLAlchemy base for backend persistence models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for module-owned SQLAlchemy models."""
