"""
API v1 router — aggregates all endpoint modules.
"""
from fastapi import APIRouter

from backend.app.api.v1.applications import router as applications_router
from backend.app.api.v1.assessments import router as assessments_router
from backend.app.api.v1.approvals import router as approvals_router
from backend.app.api.v1.governance import router as governance_router
from backend.app.api.v1.audit import router as audit_router

router = APIRouter()
router.include_router(applications_router, prefix="/applications", tags=["Applications"])
router.include_router(assessments_router, prefix="/assessments", tags=["Assessments"])
router.include_router(approvals_router, prefix="/approvals", tags=["Approvals"])
router.include_router(governance_router, prefix="/governance", tags=["Governance"])
router.include_router(audit_router, prefix="/audit", tags=["Audit"])

