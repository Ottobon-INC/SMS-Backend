from fastapi import APIRouter

from app.modules.authentication.router import router as authentication_router

router = APIRouter(prefix="/api/v1")
router.include_router(authentication_router)


@router.get("/")
def api_root() -> dict[str, str]:
    return {"status": "ok", "api": "v1"}
