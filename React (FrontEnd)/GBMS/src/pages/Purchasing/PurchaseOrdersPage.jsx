import { useCallback, useEffect, useMemo, useState } from 'react'
import { Check, ChevronLeft, ChevronRight, ClipboardList, Eye, FilePlus2, Pencil, Printer, Search, Send, X } from 'lucide-react'
import { useAuth } from '../../auth/useAuth'
import { purchaseOrderService } from '../../services/purchaseOrderService'

const statusOptions = ['DRAFT', 'SUBMITTED', 'PARTIALLY_RECEIVED', 'COMPLETED', 'CANCELLED']
const today = () => {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}
const emptyForm = () => ({ supplier_id: '', order_date: today(), expected_delivery_date: '', notes: '', items: [{ product_id: '', quantity: '1', unit_cost: '' }] })
const money = (value) => `PKR ${Number(value || 0).toLocaleString('en-PK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export default function PurchaseOrdersPage() {
  const { user } = useAuth()
  const permissions = user?.permissions || []
  const canCreate = permissions.includes('purchasing.create')
  const canEdit = permissions.includes('purchasing.update')
  const canSubmit = permissions.includes('purchasing.submit')
  const canCancel = permissions.includes('purchasing.cancel')
  const [orders, setOrders] = useState([])
  const [suppliers, setSuppliers] = useState([])
  const [products, setProducts] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [queryDraft, setQueryDraft] = useState('')
  const [filters, setFilters] = useState({ search: '', supplier_id: '', status: '', date_from: '', date_to: '' })
  const [offset, setOffset] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm] = useState(emptyForm())
  const [editingId, setEditingId] = useState(null)
  const [saving, setSaving] = useState(false)
  const [details, setDetails] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [actionId, setActionId] = useState(null)
  const limit = 20

  const loadOrders = useCallback(async () => {
    setLoading(true)
    try {
      const result = await purchaseOrderService.list({ ...filters, limit, offset })
      setOrders(result.items)
      setTotal(result.total)
      setError('')
    } catch (failure) {
      setError(failure.message || 'Could not load purchase orders.')
    } finally {
      setLoading(false)
    }
  }, [filters, offset])

  useEffect(() => {
    let active = true
    purchaseOrderService.list({ ...filters, limit, offset }).then((result) => {
      if (!active) return
      setOrders(result.items)
      setTotal(result.total)
      setError('')
    }).catch((failure) => {
      if (active) setError(failure.message || 'Could not load purchase orders.')
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [filters, offset])

  useEffect(() => {
    let active = true
    purchaseOrderService.formOptions().then((options) => {
      if (!active) return
      setSuppliers(options.suppliers)
      setProducts(options.products)
    }).catch((failure) => { if (active) setError(failure.message || 'Could not load company purchasing options.') })
    return () => { active = false }
  }, [])

  const loadOptions = async () => {
    const options = await purchaseOrderService.formOptions()
    setSuppliers(options.suppliers)
    setProducts(options.products)
  }

  const openCreate = async () => {
    setError('')
    setSuccess('')
    try {
      await loadOptions()
      setEditingId(null)
      setForm(emptyForm())
      setFormOpen(true)
    } catch (failure) {
      setError(failure.message || 'Could not load supplier and product options.')
    }
  }

  const openEdit = async (id) => {
    setError('')
    try {
      const [order, options] = await Promise.all([purchaseOrderService.get(id), purchaseOrderService.formOptions()])
      setSuppliers(options.suppliers)
      setProducts(options.products)
      setEditingId(id)
      setForm({
        supplier_id: String(order.supplier_id), order_date: String(order.order_date).slice(0, 10),
        expected_delivery_date: order.expected_delivery_date ? String(order.expected_delivery_date).slice(0, 10) : '',
        notes: order.notes || '',
        items: order.items.map((item) => ({ product_id: String(item.product_id), quantity: String(item.quantity), unit_cost: String(item.unit_cost) })),
      })
      setFormOpen(true)
    } catch (failure) {
      setError(failure.message || 'Could not load the draft purchase order.')
    }
  }

  const updateLine = (index, key, value) => setForm((current) => ({ ...current, items: current.items.map((item, i) => i === index ? { ...item, [key]: value } : item) }))
  const addLine = () => setForm((current) => ({ ...current, items: [...current.items, { product_id: '', quantity: '1', unit_cost: '' }] }))
  const removeLine = (index) => setForm((current) => ({ ...current, items: current.items.length > 1 ? current.items.filter((_, i) => i !== index) : current.items }))

  const previewTotal = useMemo(() => form.items.reduce((sum, item) => sum + (Number(item.quantity) || 0) * (Number(item.unit_cost) || 0), 0), [form.items])

  const saveOrder = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    const payload = {
      supplier_id: Number(form.supplier_id), order_date: form.order_date,
      expected_delivery_date: form.expected_delivery_date || null, notes: form.notes.trim() || null,
      items: form.items.map((item) => ({ product_id: Number(item.product_id), quantity: item.quantity, unit_cost: item.unit_cost })),
    }
    try {
      if (editingId) await purchaseOrderService.update(editingId, payload)
      else await purchaseOrderService.create(payload)
      setFormOpen(false)
      setSuccess(editingId ? 'Draft purchase order updated.' : 'Purchase order saved as draft.')
      await loadOrders()
    } catch (failure) {
      setError(failure.message || 'Could not save the purchase order.')
    } finally {
      setSaving(false)
    }
  }

  const openDetails = async (id, printable = false) => {
    setDetailLoading(true)
    setDetails({})
    try {
      const order = printable ? await purchaseOrderService.printable(id) : await purchaseOrderService.get(id)
      setDetails(order)
    } catch (failure) {
      setDetails(null)
      setError(failure.message || 'Could not load purchase order details.')
    } finally {
      setDetailLoading(false)
    }
  }

  const runAction = async (order, action) => {
    if (action === 'cancel' && !window.confirm(`Cancel ${order.purchase_order_number}? It will remain in the audit history.`)) return
    setActionId(order.purchase_order_id)
    setError('')
    try {
      if (action === 'submit') await purchaseOrderService.submit(order.purchase_order_id)
      else await purchaseOrderService.cancel(order.purchase_order_id)
      setSuccess(`${order.purchase_order_number} ${action === 'submit' ? 'submitted' : 'cancelled'}.`)
      await loadOrders()
      if (details?.purchase_order_id === order.purchase_order_id) await openDetails(order.purchase_order_id)
    } catch (failure) {
      setError(failure.message || `Could not ${action} this purchase order.`)
    } finally {
      setActionId(null)
    }
  }

  const submitSearch = (event) => {
    event.preventDefault()
    setOffset(0)
    setFilters((current) => ({ ...current, search: queryDraft.trim() }))
  }

  const renderOrderActions = (order) => <div className="flex flex-wrap justify-end gap-2">
    <button type="button" onClick={() => openDetails(order.purchase_order_id)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium hover:bg-slate-50"><Eye size={14} /> View</button>
    {order.status === 'DRAFT' && canEdit && <button type="button" onClick={() => openEdit(order.purchase_order_id)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium hover:bg-slate-50"><Pencil size={14} /> Edit</button>}
    {order.status === 'DRAFT' && canSubmit && <button type="button" disabled={actionId === order.purchase_order_id} onClick={() => runAction(order, 'submit')} className="inline-flex items-center gap-1.5 rounded-lg border border-sky-200 px-2.5 py-1.5 text-xs font-medium text-sky-800 hover:bg-sky-50 disabled:opacity-50"><Send size={14} /> Submit</button>}
    <button type="button" onClick={() => openDetails(order.purchase_order_id, true)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium hover:bg-slate-50"><Printer size={14} /> Print</button>
    {['DRAFT', 'SUBMITTED'].includes(order.status) && canCancel && <button type="button" disabled={actionId === order.purchase_order_id} onClick={() => runAction(order, 'cancel')} className="rounded-lg border border-rose-200 px-2.5 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50">Cancel</button>}
  </div>

  const statusStyle = (status) => status === 'DRAFT' ? 'bg-slate-100 text-slate-700' : status === 'SUBMITTED' ? 'bg-sky-100 text-sky-800' : status === 'CANCELLED' ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-800'

  return <section className="space-y-6 text-slate-800">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><p className="text-sm font-semibold uppercase tracking-wider text-sky-700">Company operations</p><h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Purchase orders</h1><p className="mt-2 text-sm text-slate-500">Prepare and track supplier orders. Saving or submitting an order does not change inventory.</p></div>
      {canCreate && <button type="button" onClick={openCreate} className="inline-flex items-center justify-center gap-2 rounded-xl bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-800"><FilePlus2 size={17} /> New purchase order</button>}
    </div>
    {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
    {success && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{success}</p>}

    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 p-4 sm:p-5">
        <div className="mb-4 flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-sky-700"><ClipboardList size={20} /></span><div><h2 className="font-semibold">Company purchase orders</h2><p className="text-xs text-slate-500">{total} record{total === 1 ? '' : 's'}</p></div></div>
        <form onSubmit={submitSearch} className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
          <label className="relative lg:col-span-2"><span className="sr-only">Search purchase order number</span><Search size={16} className="absolute left-3 top-3 text-slate-400" /><input value={queryDraft} onChange={(event) => setQueryDraft(event.target.value)} placeholder="Search PO number" className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm" /></label>
          <select aria-label="Filter by supplier" value={filters.supplier_id} onChange={(event) => { setOffset(0); setFilters((current) => ({ ...current, supplier_id: event.target.value })) }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">All suppliers</option>{suppliers.map((supplier) => <option key={supplier.supplier_id} value={supplier.supplier_id}>{supplier.supplier_name}</option>)}</select>
          <select aria-label="Filter by status" value={filters.status} onChange={(event) => { setOffset(0); setFilters((current) => ({ ...current, status: event.target.value })) }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">All statuses</option>{statusOptions.map((value) => <option key={value}>{value}</option>)}</select>
          <input aria-label="Date from" type="date" value={filters.date_from} onChange={(event) => { setOffset(0); setFilters((current) => ({ ...current, date_from: event.target.value })) }} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <div className="flex gap-2"><input aria-label="Date to" type="date" value={filters.date_to} onChange={(event) => { setOffset(0); setFilters((current) => ({ ...current, date_to: event.target.value })) }} className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" /><button className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50">Search</button></div>
        </form>
      </div>
      <div className="overflow-x-auto"><table className="w-full min-w-[1150px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3 font-semibold">PO number</th><th className="px-5 py-3 font-semibold">Supplier</th><th className="px-5 py-3 font-semibold">Order date</th><th className="px-5 py-3 font-semibold">Expected delivery</th><th className="px-5 py-3 font-semibold">Items</th><th className="px-5 py-3 font-semibold">Total</th><th className="px-5 py-3 font-semibold">Status</th><th className="px-5 py-3 font-semibold">Created by</th><th className="px-5 py-3 text-right font-semibold">Actions</th></tr></thead>
        <tbody className="divide-y divide-slate-100">{orders.map((order) => <tr key={order.purchase_order_id}><td className="px-5 py-4 font-mono text-xs font-semibold text-slate-800">{order.purchase_order_number}</td><td className="px-5 py-4 font-medium">{order.supplier_name}</td><td className="px-5 py-4 text-slate-600">{String(order.order_date).slice(0, 10)}</td><td className="px-5 py-4 text-slate-600">{order.expected_delivery_date ? String(order.expected_delivery_date).slice(0, 10) : '—'}</td><td className="px-5 py-4 text-slate-600">{order.item_count}</td><td className="px-5 py-4 font-medium">{money(order.total_amount)}</td><td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusStyle(order.status)}`}>{order.status.replaceAll('_', ' ')}</span></td><td className="px-5 py-4 text-slate-600">{order.created_by_name}</td><td className="px-5 py-4">{renderOrderActions(order)}</td></tr>)}
          {!loading && orders.length === 0 && <tr><td colSpan={9} className="px-5 py-14 text-center"><ClipboardList className="mx-auto text-slate-300" size={28} /><p className="mt-3 font-medium text-slate-700">No purchase orders found</p><p className="mt-1 text-sm text-slate-500">Create a draft to start tracking company purchasing.</p></td></tr>}
          {loading && <tr><td colSpan={9} className="px-5 py-12 text-center text-sm text-slate-500" role="status">Loading purchase orders…</td></tr>}</tbody></table></div>
      <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-500 sm:px-5"><span>{total === 0 ? '0 orders' : `${offset + 1}–${Math.min(offset + orders.length, total)} of ${total}`}</span><div className="flex gap-2"><button type="button" aria-label="Previous page" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - limit))} className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"><ChevronLeft size={16} /></button><button type="button" aria-label="Next page" disabled={offset + limit >= total || loading} onClick={() => setOffset(offset + limit)} className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"><ChevronRight size={16} /></button></div></div>
    </div>

    {formOpen && <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-900/40 p-3 sm:p-6"><section role="dialog" aria-modal="true" aria-labelledby="purchase-order-form-title" className="max-h-[94vh] w-full max-w-5xl overflow-y-auto rounded-2xl bg-white shadow-xl"><header className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-200 bg-white p-5 sm:p-6"><div><p className="text-xs font-semibold uppercase tracking-wider text-sky-700">Purchasing</p><h2 id="purchase-order-form-title" className="mt-1 text-xl font-semibold">{editingId ? 'Edit draft purchase order' : 'Create purchase order'}</h2><p className="mt-1 text-sm text-slate-500">Prices are stored as purchase costs. Inventory changes only when goods are received in a future phase.</p></div><button type="button" aria-label="Close purchase order form" onClick={() => setFormOpen(false)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button></header>
      <form onSubmit={saveOrder} className="space-y-5 p-5 sm:p-6"><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-sm font-medium">Supplier *<select required value={form.supplier_id} onChange={(event) => setForm({ ...form, supplier_id: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2"><option value="">Choose a supplier</option>{suppliers.filter((supplier) => supplier.supplier_status === 'ACTIVE').map((supplier) => <option key={supplier.supplier_id} value={supplier.supplier_id}>{supplier.supplier_name} · {supplier.supplier_code}</option>)}</select></label>
        <label className="text-sm font-medium">Order date *<input required type="date" value={form.order_date} onChange={(event) => setForm({ ...form, order_date: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
        <label className="text-sm font-medium">Expected delivery<input type="date" min={form.order_date} value={form.expected_delivery_date} onChange={(event) => setForm({ ...form, expected_delivery_date: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
      </div>
      <div className="overflow-x-auto rounded-xl border border-slate-200"><table className="w-full min-w-[740px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-3">Product</th><th className="px-3 py-3">Qty</th><th className="px-3 py-3">Unit cost (PKR)</th><th className="px-3 py-3 text-right">Line total</th><th className="px-3 py-3" /></tr></thead><tbody className="divide-y divide-slate-100">{form.items.map((item, index) => { const product = products.find((candidate) => String(candidate.product_id) === item.product_id); return <tr key={`po-line-${index}`}><td className="px-3 py-3"><select required value={item.product_id} onChange={(event) => updateLine(index, 'product_id', event.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"><option value="">Select catalogue product</option>{products.map((option) => <option key={option.product_id} value={option.product_id}>{option.sku} · {option.product_name}{[option.variant_size, option.variant_color].filter(Boolean).length ? ` · ${[option.variant_size, option.variant_color].filter(Boolean).join(' / ')}` : ''}</option>)}</select>{product && <p className="mt-1 text-xs text-slate-500">{product.product_type.replaceAll('_', ' ')} · {product.unit_code}</p>}</td><td className="px-3 py-3"><input required type="number" min="0.001" step="0.001" value={item.quantity} onChange={(event) => updateLine(index, 'quantity', event.target.value)} className="w-28 rounded-lg border border-slate-300 px-3 py-2" /></td><td className="px-3 py-3"><input required type="number" min="0" step="0.01" value={item.unit_cost} onChange={(event) => updateLine(index, 'unit_cost', event.target.value)} className="w-36 rounded-lg border border-slate-300 px-3 py-2" /></td><td className="px-3 py-3 text-right font-medium">{money((Number(item.quantity) || 0) * (Number(item.unit_cost) || 0))}</td><td className="px-3 py-3 text-right"><button type="button" disabled={form.items.length === 1} onClick={() => removeLine(index)} className="rounded-lg px-2 py-1 text-xs text-rose-700 disabled:opacity-30">Remove</button></td></tr> })}</tbody></table></div>
      <div className="flex flex-wrap items-center justify-between gap-3"><button type="button" onClick={addLine} disabled={form.items.length >= 100} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50">+ Add item</button><div className="text-right"><p className="text-xs uppercase tracking-wide text-slate-500">Subtotal / total</p><p className="text-xl font-semibold">{money(previewTotal)}</p></div></div>
      <label className="block text-sm font-medium">Notes / terms<textarea maxLength={1000} rows={3} value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
      <div className="flex justify-end gap-3 border-t border-slate-100 pt-4"><button type="button" onClick={() => setFormOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">Cancel</button><button disabled={saving || suppliers.length === 0 || products.length === 0} className="inline-flex items-center gap-2 rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? 'Saving…' : <><Check size={16} /> Save draft</>}</button></div>
      </form></section></div>}

      {(details || detailLoading) && <div className="fixed inset-0 z-[85] flex items-center justify-center bg-slate-900/40 p-3 sm:p-6" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setDetails(null) }}><section role="dialog" aria-modal="true" aria-labelledby="po-detail-title" className="max-h-[94vh] w-full max-w-4xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl sm:p-7"><div className="no-print flex items-start justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-sky-700">Purchase order</p><h2 id="po-detail-title" className="mt-1 text-xl font-semibold">{details?.purchase_order_number || 'Loading…'}</h2></div><button type="button" aria-label="Close purchase order details" onClick={() => setDetails(null)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button></div>{detailLoading ? <p className="py-10 text-center text-sm text-slate-500" role="status">Loading details…</p> : details && <div id="purchase-order-print" className="mt-5"><div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-4"><div><p className="text-lg font-bold tracking-wide text-sky-800">GBMS</p><p className="text-sm text-slate-500">Purchase order · PKR</p></div><div className="text-right"><h3 className="text-xl font-bold">{details.purchase_order_number}</h3><span className={`mt-2 inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusStyle(details.status)}`}>{details.status.replaceAll('_', ' ')}</span></div></div><dl className="grid gap-3 py-4 text-sm sm:grid-cols-2 lg:grid-cols-4"><div><dt className="text-xs uppercase text-slate-500">Supplier</dt><dd className="mt-1 font-semibold">{details.supplier_name}</dd></div><div><dt className="text-xs uppercase text-slate-500">Order date</dt><dd className="mt-1">{String(details.order_date).slice(0, 10)}</dd></div><div><dt className="text-xs uppercase text-slate-500">Expected delivery</dt><dd className="mt-1">{details.expected_delivery_date ? String(details.expected_delivery_date).slice(0, 10) : '—'}</dd></div><div><dt className="text-xs uppercase text-slate-500">Prepared by</dt><dd className="mt-1">{details.created_by_name}</dd></div></dl>{details.supplier_contact && <div className="mb-4 rounded-xl bg-slate-50 p-4 text-sm"><h4 className="font-semibold">Supplier contact</h4><p className="mt-1">{details.supplier_contact.contact_person || details.supplier_contact.name}{details.supplier_contact.email ? ` · ${details.supplier_contact.email}` : ""}{details.supplier_contact.phone ? ` · ${details.supplier_contact.phone}` : ""}</p><p className="mt-1 text-slate-600">{[details.supplier_contact.address, details.supplier_contact.city, details.supplier_contact.country].filter(Boolean).join(", ") || "No supplier address on file"}</p>{details.supplier_contact.payment_terms && <p className="mt-1 text-xs text-slate-500">Payment terms: {details.supplier_contact.payment_terms}</p>}</div>}<div className="overflow-x-auto rounded-xl border border-slate-200"><table className="w-full min-w-[650px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-3 py-3">SKU</th><th className="px-3 py-3">Description</th><th className="px-3 py-3">Quantity</th><th className="px-3 py-3">Unit cost</th><th className="px-3 py-3 text-right">Amount</th></tr></thead><tbody className="divide-y divide-slate-100">{details.items.map((item) => <tr key={item.purchase_order_item_id}><td className="px-3 py-3 font-mono text-xs">{item.sku}</td><td className="px-3 py-3">{item.product_name}<p className="mt-1 text-xs text-slate-500">{[item.variant_design, item.variant_size, item.variant_color].filter(Boolean).join(" · ") || "—"}</p></td><td className="px-3 py-3">{item.quantity} {item.unit_code}</td><td className="px-3 py-3">{money(item.unit_cost)}</td><td className="px-3 py-3 text-right font-medium">{money(item.line_total)}</td></tr>)}</tbody></table></div><div className="ml-auto mt-4 max-w-xs border-t border-slate-200 pt-3 text-right"><p className="text-sm text-slate-500">Subtotal <strong className="ml-4 text-slate-800">{money(details.subtotal)}</strong></p><p className="mt-2 text-lg font-bold">Total <span className="ml-4">{money(details.total_amount)}</span></p></div>{details.notes && <div className="mt-4"><p className="text-xs font-semibold uppercase text-slate-500">Notes / terms</p><p className="mt-1 whitespace-pre-wrap text-sm">{details.notes}</p></div>}<div className="no-print mt-4 rounded-xl bg-slate-50 p-4"><h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Status history</h4><ol className="mt-2 space-y-2">{details.status_history.map((entry, index) => <li key={`${entry.status}-${index}`} className="flex flex-wrap justify-between gap-x-4 text-xs"><span><strong>{entry.status.replaceAll('_', ' ')}</strong> · {entry.changed_by_name}{entry.note ? ` · ${entry.note}` : ''}</span><time className="text-slate-500">{new Date(entry.changed_at).toLocaleString()}</time></li>)}</ol></div><p className="mt-6 border-t border-slate-200 pt-3 text-xs text-slate-500">This document is a purchase order, not a goods receipt or payment receipt. Inventory is not changed by this order.</p><div className="no-print mt-5 flex flex-wrap justify-end gap-2"><button type="button" onClick={() => window.print()} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm"><Printer size={16} /> Print purchase order</button>{details.status === 'DRAFT' && canEdit && <button type="button" onClick={() => { setDetails(null); openEdit(details.purchase_order_id) }} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm"><Pencil size={16} /> Edit draft</button>}{details.status === 'DRAFT' && canSubmit && <button type="button" onClick={() => runAction(details, 'submit')} className="inline-flex items-center gap-2 rounded-lg bg-sky-700 px-3 py-2 text-sm font-semibold text-white"><Send size={16} /> Submit</button>}{['DRAFT', 'SUBMITTED'].includes(details.status) && canCancel && <button type="button" onClick={() => runAction(details, 'cancel')} className="rounded-lg border border-rose-200 px-3 py-2 text-sm text-rose-700">Cancel order</button>}</div></div>}</section><style>{'@media print { body * { visibility: hidden !important; } #purchase-order-print, #purchase-order-print * { visibility: visible !important; } #purchase-order-print { position: absolute; left: 0; top: 0; width: 100%; margin: 0; padding: 12mm; color: #111827; } .no-print { display: none !important; } }'}</style></div>}
  </section>
}
