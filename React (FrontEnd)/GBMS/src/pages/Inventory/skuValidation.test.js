import assert from 'node:assert/strict'
import test from 'node:test'
import { SKU_PATTERN } from './skuValidation.js'

test('SKU pattern is valid in modern HTML v-mode and accepts supported SKU characters', () => {
  const pattern = new RegExp(`^(?:${SKU_PATTERN})$`, 'v')
  for (const value of ['FAB-001/BLUE', 'FAB.01', 'A_B']) assert.equal(pattern.test(value), true)
  for (const value of ['_BAD', 'FAB 01', '']) assert.equal(pattern.test(value), false)
})
