from fastapi import APIRouter

from app.modules.academic_structure.router import router as academic_structure_router
from app.modules.authentication.router import router as auth_router
from app.modules.branches.router import router as branches_router
from app.modules.examinations.router import router as examinations_router
from app.modules.students.router import router as students_router
from app.modules.users.router import router as users_router

router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(branches_router)
router.include_router(students_router)
router.include_router(academic_structure_router)
router.include_router(examinations_router)


@router.get("/")
def api_root() -> dict[str, str]:
    return {"status": "ok", "api": "v1"}
