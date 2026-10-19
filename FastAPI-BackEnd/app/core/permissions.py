"""Permission identifiers and role defaults used by API authorization."""

PERMISSION_LABELS = {
    "dashboard.view": "View dashboard",
    "dashboard.company_overview": "View company overview metrics",
    "users.view": "View company users",
    "users.create": "Create company users",
    "users.update": "Edit company users",
    "users.deactivate": "Activate or deactivate users",
    "users.delete": "Permanently delete company users",
    "users.assign_role": "Assign roles and permissions",
    "inventory.view": "View inventory",
    "inventory.create": "Create inventory records",
    "inventory.update": "Edit inventory records",
    "suppliers.view": "View company suppliers",
    "suppliers.create": "Create company suppliers",
    "suppliers.update": "Edit company suppliers",
    "suppliers.deactivate": "Activate or deactivate suppliers",
}

WORKER_ROLE = "WORKER"
ALL_PERMISSIONS = tuple(PERMISSION_LABELS)
COMPANY_USER_ROLES = ("SUB_ADMIN", "INVENTORY_USER", WORKER_ROLE)
COMPANY_ADMIN_PERMISSIONS = frozenset(
    {
        "dashboard.view",
        "dashboard.company_overview",
        "users.view",
        "users.create",
        "users.update",
        "users.deactivate",
        "users.delete",
        "users.assign_role",
        "inventory.view",
        "inventory.create",
        "inventory.update",
        "suppliers.view",
        "suppliers.create",
        "suppliers.update",
        "suppliers.deactivate",
    }
)
LEGACY_INVENTORY_PERMISSIONS = frozenset(
    {"dashboard.view", "inventory.view", "inventory.create", "inventory.update"}
)


def effective_permissions(role_name, configured, assigned=()):
    if role_name == "SUPER_ADMIN":
        return list(ALL_PERMISSIONS)
    if role_name == WORKER_ROLE:
        return ["dashboard.view"]
    if role_name == "COMPANY_ADMIN" and not configured:
        return sorted(COMPANY_ADMIN_PERMISSIONS)
    if role_name == "COMPANY_ADMIN":
        return sorted({"dashboard.view", "dashboard.company_overview", *assigned})
    if not configured and role_name in COMPANY_USER_ROLES:
        return sorted(LEGACY_INVENTORY_PERMISSIONS)
    return sorted({"dashboard.view", *assigned})


def has_permission(user, permission_code):
    if user.get("role_name") == "SUPER_ADMIN":
        return True
    return permission_code in user.get("permissions", ())
