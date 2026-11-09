import test from 'node:test'
import assert from 'node:assert/strict'
import { isLowStockProduct } from './stockPresentation.js'

test('low stock is inclusive of reorder level', () => {
  assert.equal(isLowStockProduct({ is_active: true, quantity_on_hand: 80, reorder_level: 100 }), true)
  assert.equal(isLowStockProduct({ is_active: true, quantity_on_hand: 100, reorder_level: 100 }), true)
  assert.equal(isLowStockProduct({ is_active: true, quantity_on_hand: 101, reorder_level: 100 }), false)
})

test('inactive products and authoritative API values are respected', () => {
  assert.equal(isLowStockProduct({ is_active: false, quantity_on_hand: 0, reorder_level: 1 }), false)
  assert.equal(isLowStockProduct({ is_active: true, is_low_stock: false, quantity_on_hand: 0, reorder_level: 1 }), false)
})
