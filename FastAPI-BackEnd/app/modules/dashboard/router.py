"""Company dashboard endpoints."""

from fastapi import APIRouter, Depends

from app.dependencies.permissions import require_company_permission
from app.modules.dashboard import service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/company-overview")
def company_overview(user=Depends(require_company_permission("dashboard.company_overview"))):
    return service.company_overview(user["company_id"])
