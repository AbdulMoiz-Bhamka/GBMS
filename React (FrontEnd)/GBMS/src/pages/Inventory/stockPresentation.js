export function isLowStockProduct(product) {
  if (typeof product?.is_low_stock === 'boolean') return product.is_low_stock
  return Boolean(product?.is_active) && Number(product?.quantity_on_hand) <= Number(product?.reorder_level)
}
