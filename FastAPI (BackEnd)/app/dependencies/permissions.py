from fastapi import Depends, HTTPException

from app.dependencies.auth import get_current_user


def require_super_admin(user=Depends(get_current_user)):
    if user["role_name"] != "SUPER_ADMIN":
        raise HTTPException(
            status_code=403, detail="Platform Super Admin access is required."
        )
    return user


def require_company_user(user=Depends(get_current_user)):
    inventory_roles = {"COMPANY_ADMIN", "SUB_ADMIN", "INVENTORY_USER"}
    if user["role_name"] not in inventory_roles or user["company_id"] is None:
        raise HTTPException(
            status_code=403,
            detail="An authorized company inventory role is required.",
        )
    return user
