from fastapi import APIRouter

from app.modules.academic_structure.router import router as academic_structure_router
from app.modules.attendance.router import router as attendance_router
from app.modules.authentication.router import router as authentication_router
from app.modules.branches.router import router as branches_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.examinations.router import router as examinations_router
from app.modules.fees.router import router as fees_router
from app.modules.imports.router import fee_router as fee_imports_router
from app.modules.imports.router import router as imports_router
from app.modules.notifications.router import router as notifications_router
from app.modules.students.router import router as students_router
from app.modules.users.router import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(academic_structure_router)
router.include_router(attendance_router)
router.include_router(authentication_router)
router.include_router(branches_router)
router.include_router(dashboard_router)
router.include_router(examinations_router)
router.include_router(fees_router)
router.include_router(students_router)
router.include_router(users_router)
router.include_router(imports_router)
router.include_router(fee_imports_router)
router.include_router(notifications_router)


@router.get("/")
def api_root() -> dict[str, str]:
    return {"status": "ok", "api": "v1"}
