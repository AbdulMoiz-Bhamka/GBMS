export const COMPANY_MODULES = [
  { path: '/users', permission: 'users.view' },
  { path: '/inventory', permission: 'inventory.view' },
  { path: '/suppliers', permission: 'suppliers.view' },
  { path: '/purchase-orders', permission: 'purchasing.view' },
]

export function canSeeCompanyModule(user, permission) {
  return user?.company_id != null
    && Array.isArray(user.permissions)
    && user.permissions.includes(permission)
}

export function visibleCompanyModulePaths(user) {
  return COMPANY_MODULES
    .filter(({ permission }) => canSeeCompanyModule(user, permission))
    .map(({ path }) => path)
}
