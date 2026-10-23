// src/pages/Inventory/InventoryPage.jsx
import { useCallback, useEffect, useState } from 'react'
import { Barcode, ChevronLeft, ChevronRight, Package, Pencil, Plus, Power, Printer, X } from 'lucide-react'
import { inventoryService } from '../../services/inventoryService'
import { useAuth } from '../../auth/useAuth'

const emptyProduct = {
  sku: '', product_name: '', product_type: 'RAW_MATERIAL', category_id: '', quantity_on_hand: '0',
  unit_id: '', description: '', reorder_level: '0', variant_design: '', variant_size: '',
  variant_color: '', selling_price: '',
}

export default function InventoryPage() {
  const { user } = useAuth()
  const canCreate = user?.permissions?.includes('inventory.create')
  const canUpdate = user?.permissions?.includes('inventory.update')
  const canManageBarcodes = user?.permissions?.includes('inventory.barcode.manage')
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [units, setUnits] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [optionsError, setOptionsError] = useState('')
  const [success, setSuccess] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [offset, setOffset] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyProduct)
  const [categoryFormOpen, setCategoryFormOpen] = useState(false)
  const [categoryForm, setCategoryForm] = useState({ category_name: '', description: '' })
  const [categorySaving, setCategorySaving] = useState(false)
  const [barcodeLabel, setBarcodeLabel] = useState(null)
  const [barcodeLoadingId, setBarcodeLoadingId] = useState(null)
  const limit = 20

  const loadProducts = useCallback(async (requestedOffset = offset) => {
    try {
      const result = await inventoryService.products({
        search,
        category_id: categoryId || undefined,
        limit,
        offset: requestedOffset,
      })
      setProducts(result.items)
      setTotal(result.total)
      setError('')
    } catch (failure) {
      setError(failure.message || 'Could not load products.')
    } finally {
      setLoading(false)
    }
  }, [categoryId, offset, search])

  useEffect(() => {
    let active = true
    inventoryService.products({ search, category_id: categoryId || undefined, limit, offset }).then((result) => {
      if (!active) return
      setProducts(result.items)
      setTotal(result.total)
      setError('')
    }).catch((failure) => {
      if (active) setError(failure.message || 'Could not load products.')
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [search, categoryId, offset])

  useEffect(() => {
    let active = true
    Promise.all([inventoryService.categories(), inventoryService.units()])
      .then(([companyCategories, availableUnits]) => {
        if (active) {
          setCategories(companyCategories)
          setUnits(availableUnits)
          setOptionsError('')
        }
      })
      .catch((failure) => { if (active) setOptionsError(failure.message || 'Could not load inventory options.') })
    return () => { active = false }
  }, [])

  const openCreate = () => {
    setEditingId(null)
    setForm(emptyProduct)
    setError('')
    setSuccess('')
    setFormOpen(true)
  }

  const openEdit = async (productId) => {
    setError('')
    setSuccess('')
    try {
      const product = await inventoryService.getProduct(productId)
      setEditingId(productId)
      setForm({
        sku: product.sku,
        product_name: product.product_name,
        product_type: product.product_type,
        category_id: product.category_id ? String(product.category_id) : '',
        unit_id: String(product.unit_id),
        description: product.description || '',
        quantity_on_hand: String(product.quantity_on_hand ?? 0),
        reorder_level: String(product.reorder_level ?? 0),
        variant_design: product.variant_design || '',
        variant_size: product.variant_size || '',
        variant_color: product.variant_color || '',
        selling_price: product.selling_price == null ? '' : String(product.selling_price),
      })
      setFormOpen(true)
    } catch (failure) {
      setError(failure.message || 'Could not load product details.')
    }
  }

  const saveProduct = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    const payload = {
      sku: form.sku.trim(),
      product_name: form.product_name.trim(),
      product_type: form.product_type,
      category_id: form.category_id ? Number(form.category_id) : null,
      unit_id: Number(form.unit_id),
      description: form.description.trim() || null,
      quantity_on_hand: form.quantity_on_hand,
      reorder_level: form.reorder_level,
      variant_design: form.variant_design.trim() || null,
      variant_size: form.variant_size.trim() || null,
      variant_color: form.variant_color.trim() || null,
      selling_price: form.product_type === 'FINISHED_GOOD' && form.selling_price !== '' ? form.selling_price : null,
    }
    try {
      if (editingId) {
        await inventoryService.updateProduct(editingId, payload)
        setSuccess('Product updated.')
        setFormOpen(false)
        await loadProducts()
      } else {
        await inventoryService.createProduct(payload)
        setSuccess('Product created.')
        setFormOpen(false)
        setOffset(0)
        await loadProducts(0)
      }
    } catch (failure) {
      setError(failure.message || 'Could not save product.')
    } finally {
      setSaving(false)
    }
  }

  const createOrShowBarcode = async (product) => {
    setBarcodeLoadingId(product.product_id)
    setError('')
    try {
      const label = await inventoryService.generateBarcode(product.product_id)
      setBarcodeLabel(label)
      await loadProducts()
    } catch (failure) {
      setError(failure.message || 'Could not load the barcode label.')
    } finally {
      setBarcodeLoadingId(null)
    }
  }

  const toggleStatus = async (product) => {
    const isActive = !product.is_active
    const action = isActive ? 'activate' : 'deactivate'
    if (!window.confirm(`Are you sure you want to ${action} ${product.product_name}?`)) return
    setError('')
    setSuccess('')
    try {
      await inventoryService.setProductStatus(product.product_id, isActive)
      setSuccess(`${product.product_name} is now ${isActive ? 'active' : 'inactive'}.`)
      await loadProducts()
    } catch (failure) {
      setError(failure.message || 'Could not update product status.')
    }
  }

  const addCategory = async (event) => {
    event.preventDefault()
    setCategorySaving(true)
    setError('')
    setSuccess('')
    try {
      const created = await inventoryService.createCategory({
        category_name: categoryForm.category_name.trim(),
        description: categoryForm.description.trim() || null,
      })
      setCategories((current) => [...current, created].sort((a, b) => a.category_name.localeCompare(b.category_name)))
      setForm((current) => ({ ...current, category_id: String(created.category_id) }))
      setCategoryForm({ category_name: '', description: '' })
      setCategoryFormOpen(false)
      setSuccess('Category created for your company.')
    } catch (failure) {
      setError(failure.message || 'Could not create category.')
    } finally {
      setCategorySaving(false)
    }
  }

  const submitSearch = (event) => {
    event.preventDefault()
    setOffset(0)
    setSearch(searchInput.trim())
  }

  return (
    <section className="space-y-6 text-slate-800">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-sky-700">Company operations</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Inventory</h1>
          <p className="mt-2 text-sm text-slate-500">Manage this company’s product catalogue and reorder thresholds.</p>
        </div>
        {canCreate && <button type="button" onClick={openCreate} disabled={units.length === 0} className="inline-flex items-center justify-center gap-2 rounded-xl bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-50"><Plus size={17} /> Add product</button>}
      </div>

      {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      {optionsError && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{optionsError}</p>}
      {success && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{success}</p>}

      {formOpen && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-5 flex items-start justify-between gap-4"><div><h2 className="font-semibold">{editingId ? 'Edit product' : 'Add product'}</h2><p className="mt-1 text-sm text-slate-500">Product records are saved to your assigned company.</p></div><button type="button" aria-label="Close product form" onClick={() => setFormOpen(false)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button></div>
          <form onSubmit={saveProduct}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className="text-sm font-medium text-slate-700">SKU *<input required maxLength={60} pattern="[A-Za-z0-9][A-Za-z0-9._/-]{0,59}" value={form.sku} onChange={(event) => setForm({ ...form, sku: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
            <label className="text-sm font-medium text-slate-700">Product name *<input required maxLength={180} value={form.product_name} onChange={(event) => setForm({ ...form, product_name: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
            <label className="text-sm font-medium text-slate-700">Product type *<select required value={form.product_type} onChange={(event) => setForm({ ...form, product_type: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal outline-none focus:border-sky-500"><option value="RAW_MATERIAL">Raw material</option><option value="FINISHED_GOOD">Finished good</option></select></label>
            {form.product_type === 'FINISHED_GOOD' && <>
              <label className="text-sm font-medium text-slate-700">Design / model<input maxLength={100} value={form.variant_design} onChange={(event) => setForm({ ...form, variant_design: event.target.value })} placeholder="e.g. Summer Floral 01" className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500" /></label>
              <label className="text-sm font-medium text-slate-700">Size<input maxLength={40} value={form.variant_size} onChange={(event) => setForm({ ...form, variant_size: event.target.value })} placeholder="e.g. Medium" className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500" /></label>
              <label className="text-sm font-medium text-slate-700">Colour<input maxLength={50} value={form.variant_color} onChange={(event) => setForm({ ...form, variant_color: event.target.value })} placeholder="e.g. Navy" className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500" /></label>
              <label className="text-sm font-medium text-slate-700">Selling price (PKR)<input type="number" min="0" step="0.01" value={form.selling_price} onChange={(event) => setForm({ ...form, selling_price: event.target.value })} placeholder="Set before generating a barcode" className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500" /></label>
            </>}
            <label className="text-sm font-medium text-slate-700">Unit of measure *<select required value={form.unit_id} onChange={(event) => setForm({ ...form, unit_id: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal outline-none focus:border-sky-500"><option value="">Select a unit</option>{units.map((unit) => <option key={unit.unit_id} value={unit.unit_id}>{unit.unit_name} ({unit.symbol || unit.unit_code})</option>)}</select></label>
            <div><label htmlFor="product-category" className="text-sm font-medium text-slate-700">Category</label><select id="product-category" value={form.category_id} onChange={(event) => setForm({ ...form, category_id: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-500"><option value="">No category</option>{categories.map((category) => <option key={category.category_id} value={category.category_id}>{category.category_name}</option>)}</select>{canCreate && <button type="button" onClick={() => setCategoryFormOpen((open) => !open)} className="mt-1 text-xs font-semibold text-sky-700 hover:text-sky-900">{categoryFormOpen ? 'Cancel new category' : '+ Create a category'}</button>}</div>
            <label className="text-sm font-medium text-slate-700">Quantity on hand<input required type="number" min="0" step="0.001" value={form.quantity_on_hand} onChange={(event) => setForm({ ...form, quantity_on_hand: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /><span className="mt-1 block text-xs font-normal text-slate-500">Current stock for this product. It updates the dashboard chart.</span></label>
            <label className="text-sm font-medium text-slate-700">Reorder level *<input required type="number" min="0" step="0.001" value={form.reorder_level} onChange={(event) => setForm({ ...form, reorder_level: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
            <label className="text-sm font-medium text-slate-700 sm:col-span-2 lg:col-span-3">Description<textarea rows={2} maxLength={1000} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
          </div>
          <div className="mt-5 flex justify-end gap-3"><button type="button" onClick={() => setFormOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button><button disabled={saving || units.length === 0 || (editingId ? !canUpdate : !canCreate)} className="rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:opacity-50">{saving ? 'Saving…' : editingId ? 'Save changes' : 'Create product'}</button></div>
          </form>
          {categoryFormOpen && canCreate && <form className="mt-5 grid gap-3 rounded-xl border border-sky-100 bg-sky-50/50 p-4 sm:grid-cols-[1fr_1.5fr_auto] sm:items-end" onSubmit={addCategory}>
            <label className="text-sm font-medium text-slate-700">New category *<input required maxLength={100} value={categoryForm.category_name} onChange={(event) => setCategoryForm({ ...categoryForm, category_name: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal" /></label>
            <label className="text-sm font-medium text-slate-700">Description<input maxLength={300} value={categoryForm.description} onChange={(event) => setCategoryForm({ ...categoryForm, description: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal" /></label>
            <button disabled={categorySaving} className="rounded-lg border border-sky-200 bg-white px-3 py-2 text-sm font-semibold text-sky-800 disabled:opacity-50">{categorySaving ? 'Adding…' : 'Add category'}</button>
          </form>}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-sky-700"><Package size={20} /></span><div><h2 className="font-semibold">Products</h2><p className="text-xs text-slate-500">{total} products in this company</p></div></div>
          <div className="flex flex-col gap-2 sm:flex-row"><form onSubmit={submitSearch} className="flex gap-2"><label htmlFor="product-search" className="sr-only">Search products</label><input id="product-search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search SKU, name or barcode" className="min-w-0 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500" /><button className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50">Search</button></form><label htmlFor="category-filter" className="sr-only">Filter by category</label><select id="category-filter" value={categoryId} onChange={(event) => { setOffset(0); setCategoryId(event.target.value) }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">All categories</option>{categories.map((category) => <option key={category.category_id} value={category.category_id}>{category.category_name}</option>)}</select></div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1160px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3 font-semibold">SKU</th><th className="px-5 py-3 font-semibold">Product / variant</th><th className="px-5 py-3 font-semibold">Category</th><th className="px-5 py-3 font-semibold">Type</th><th className="px-5 py-3 font-semibold">Unit</th><th className="px-5 py-3 font-semibold">On hand</th><th className="px-5 py-3 font-semibold">Selling price</th><th className="px-5 py-3 font-semibold">Barcode</th><th className="px-5 py-3 font-semibold">Status</th><th className="px-5 py-3 text-right font-semibold">Actions</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {products.map((product) => <tr key={product.product_id}>
                <td className="px-5 py-4 font-mono text-xs text-slate-600">{product.sku}</td><td className="px-5 py-4 font-semibold text-slate-800">{product.product_name}<p className="mt-1 text-xs font-normal text-slate-500">{[product.variant_design, product.variant_size, product.variant_color].filter(Boolean).join(' · ') || 'No variant details'}</p></td><td className="px-5 py-4 text-slate-600">{product.category_name || '—'}</td><td className="px-5 py-4 text-slate-600">{product.product_type === 'RAW_MATERIAL' ? 'Raw material' : 'Finished good'}</td><td className="px-5 py-4 text-slate-600">{product.unit_name} ({product.unit_code})</td><td className="px-5 py-4 font-medium text-slate-700">{product.quantity_on_hand} {product.unit_code}</td><td className="px-5 py-4 text-slate-600">{product.selling_price == null ? '—' : `PKR ${Number(product.selling_price).toLocaleString()}`}</td><td className="px-5 py-4 font-mono text-xs text-slate-600">{product.barcode_value ? 'Generated' : product.product_type === 'FINISHED_GOOD' ? 'Not generated' : '—'}</td><td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${product.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>{product.is_active ? 'ACTIVE' : 'INACTIVE'}</span></td><td className="px-5 py-4"><div className="flex justify-end gap-2">{canUpdate && <><button type="button" onClick={() => openEdit(product.product_id)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium hover:bg-slate-50"><Pencil size={14} /> Edit</button><button type="button" onClick={() => toggleStatus(product)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium hover:bg-slate-50"><Power size={14} />{product.is_active ? 'Deactivate' : 'Activate'}</button></>}{canManageBarcodes && product.product_type === 'FINISHED_GOOD' && <button type="button" onClick={() => createOrShowBarcode(product)} disabled={barcodeLoadingId === product.product_id} className="inline-flex items-center gap-1.5 rounded-lg border border-sky-200 px-2.5 py-1.5 text-xs font-medium text-sky-800 hover:bg-sky-50 disabled:opacity-50">{product.barcode_value ? <Printer size={14} /> : <Barcode size={14} />}{barcodeLoadingId === product.product_id ? 'Loading…' : product.barcode_value ? 'Label' : 'Generate'}</button>}</div></td>
              </tr>)}
              {!loading && products.length === 0 && <tr><td colSpan={10} className="px-5 py-14 text-center"><Package className="mx-auto text-slate-300" size={28} /><p className="mt-3 font-medium text-slate-700">No products yet</p><p className="mt-1 text-sm text-slate-500">Add a product to start this company’s catalogue.</p></td></tr>}
              {loading && <tr><td colSpan={10} className="px-5 py-12 text-center text-sm text-slate-500" role="status">Loading products…</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-500 sm:px-5"><span>{total === 0 ? '0 products' : `${offset + 1}–${Math.min(offset + products.length, total)} of ${total}`}</span><div className="flex gap-2"><button type="button" aria-label="Previous page" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - limit))} className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"><ChevronLeft size={16} /></button><button type="button" aria-label="Next page" disabled={offset + limit >= total || loading} onClick={() => setOffset(offset + limit)} className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"><ChevronRight size={16} /></button></div></div>
      </div>
      {barcodeLabel && <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-900/40 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setBarcodeLabel(null) }}><section role="dialog" aria-modal="true" aria-labelledby="barcode-title" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"><div className="flex items-start justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-sky-700">Finished-garment label</p><h2 id="barcode-title" className="mt-1 text-xl font-semibold">{barcodeLabel.product_name}</h2></div><button type="button" aria-label="Close barcode label" onClick={() => setBarcodeLabel(null)} className="no-print rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button></div><div id="gbms-barcode-label" className="mt-5 border border-slate-200 p-5 text-center"><p className="font-semibold">{barcodeLabel.product_name}</p><p className="mt-1 text-xs text-slate-600">SKU {barcodeLabel.sku}{[barcodeLabel.variant_design, barcodeLabel.variant_size, barcodeLabel.variant_color].filter(Boolean).length ? ` · ${[barcodeLabel.variant_design, barcodeLabel.variant_size, barcodeLabel.variant_color].filter(Boolean).join(' · ')}` : ''}</p><img className="mx-auto mt-4 max-w-full" alt={`Code 128 barcode ${barcodeLabel.barcode_value}`} src={`data:image/svg+xml;base64,${barcodeLabel.barcode_svg_base64}`} /><p className="mt-1 font-mono text-xs tracking-wider">{barcodeLabel.barcode_value}</p><p className="mt-2 text-sm font-semibold">PKR {Number(barcodeLabel.selling_price).toLocaleString()}</p></div><div className="no-print mt-5 flex justify-end gap-2"><button type="button" onClick={() => setBarcodeLabel(null)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">Close</button><button type="button" onClick={() => window.print()} className="inline-flex items-center gap-2 rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white"><Printer size={16} /> Print label</button></div><style>{'@media print { body * { visibility: hidden !important; } #gbms-barcode-label, #gbms-barcode-label * { visibility: visible !important; } #gbms-barcode-label { position: absolute; left: 0; top: 0; width: 80mm; border: 0 !important; box-shadow: none !important; } .no-print { display: none !important; } }'}</style></section></div>}
    </section>
  )
}
