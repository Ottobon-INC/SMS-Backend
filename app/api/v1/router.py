from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")


@router.get("/")
def api_root() -> dict[str, str]:
    return {"status": "ok", "api": "v1"}
