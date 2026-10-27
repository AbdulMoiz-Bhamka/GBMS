import assert from 'node:assert/strict'
import test from 'node:test'
import { visibleCompanyModulePaths } from './navigationAccess.js'

test('a company admin sees each implemented module granted by the backend', () => {
  const user = {
    role_name: 'COMPANY_ADMIN',
    company_id: 41,
    permissions: ['users.view', 'inventory.view', 'suppliers.view', 'purchasing.view'],
  }

  assert.deepEqual(visibleCompanyModulePaths(user), [
    '/users', '/inventory', '/suppliers', '/purchase-orders',
  ])
})

test('navigation hides modules without permission and never shows tenant modules without a company', () => {
  assert.deepEqual(visibleCompanyModulePaths({
    role_name: 'INVENTORY_USER', company_id: 41, permissions: ['inventory.view'],
  }), ['/inventory'])
  assert.deepEqual(visibleCompanyModulePaths({
    role_name: 'SUPER_ADMIN', company_id: null, permissions: ['inventory.view'],
  }), [])
})
