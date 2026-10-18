from fastapi import Depends, HTTPException

from app.dependencies.auth import get_current_user
from app.core.permissions import has_permission


def require_super_admin(user=Depends(get_current_user)):
    if user["role_name"] != "SUPER_ADMIN":
        raise HTTPException(
            status_code=403, detail="Platform Super Admin access is required."
        )
    return user


def require_company_user(user=Depends(get_current_user)):
    if (
        user["company_id"] is None
        or not has_permission(user, "inventory.view")
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access inventory.",
        )
    return user


def require_permission(permission_code):
    def dependency(user=Depends(get_current_user)):
        if not has_permission(user, permission_code):
            raise HTTPException(
                status_code=403,
                detail=f"Permission required: {permission_code}.",
            )
        return user

    return dependency


def require_company_permission(permission_code):
    def dependency(user=Depends(get_current_user)):
        if user.get("company_id") is None or not has_permission(user, permission_code):
            raise HTTPException(
                status_code=403,
                detail=f"Company permission required: {permission_code}.",
            )
        return user

    return dependency
