from fastapi import APIRouter

from app.core.database.session import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "student-management-backend"}


@router.get("/health/database")
def database_health() -> dict[str, str]:
    check_database_connection()
    return {"status": "healthy", "database": "connected"}
