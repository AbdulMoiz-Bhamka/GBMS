import { useCallback, useEffect, useState } from 'react'
import { Building2, ChevronLeft, ChevronRight, Eye, Pencil, Plus, Power, Search, Truck, X } from 'lucide-react'
import { useAuth } from '../../auth/useAuth'
import { supplierService } from '../../services/supplierService'

const emptySupplier = {
  supplier_code: '', supplier_name: '', contact_person: '', email: '', phone: '',
  alternate_phone: '', address: '', city: '', country: '',
  tax_registration_number: '', payment_terms: '', notes: '',
}

const fields = [
  ['supplier_code', 'Supplier code', { required: true, maxLength: 40 }],
  ['supplier_name', 'Supplier name', { required: true, maxLength: 180 }],
  ['contact_person', 'Contact person', { maxLength: 160 }],
  ['email', 'Email', { type: 'email', maxLength: 254 }],
  ['phone', 'Phone', { type: 'tel', maxLength: 40 }],
  ['alternate_phone', 'Alternate phone', { type: 'tel', maxLength: 40 }],
  ['city', 'City', { maxLength: 100 }],
  ['country', 'Country', { maxLength: 100 }],
  ['tax_registration_number', 'Tax registration number', { maxLength: 50 }],
  ['payment_terms', 'Payment terms', { maxLength: 100 }],
]

function display(value) {
  return value || '—'
}

export default function SuppliersPage() {
  const { user } = useAuth()
  const canCreate = user?.permissions?.includes('suppliers.create')
  const canUpdate = user?.permissions?.includes('suppliers.update')
  const canChangeStatus = user?.permissions?.includes('suppliers.deactivate')
  const [suppliers, setSuppliers] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [offset, setOffset] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptySupplier)
  const [details, setDetails] = useState(null)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const limit = 20

  const loadSuppliers = useCallback(async (requestedOffset = offset) => {
    setLoading(true)
    try {
      const result = await supplierService.list({ search, supplier_status: statusFilter, limit, offset: requestedOffset })
      setSuppliers(result.items)
      setTotal(result.total)
      setError('')
    } catch (failure) {
      setError(failure.message || 'Could not load suppliers.')
    } finally {
      setLoading(false)
    }
  }, [offset, search, statusFilter])

  useEffect(() => {
    let active = true
    supplierService.list({ search, supplier_status: statusFilter, limit, offset }).then((result) => {
      if (!active) return
      setSuppliers(result.items)
      setTotal(result.total)
      setError('')
    }).catch((failure) => {
      if (active) setError(failure.message || 'Could not load suppliers.')
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [offset, search, statusFilter])

  const openCreate = () => {
    setEditingId(null)
    setForm(emptySupplier)
    setError('')
    setSuccess('')
    setFormOpen(true)
  }

  const openEdit = (supplier) => {
    setEditingId(supplier.supplier_id)
    setForm(Object.fromEntries(Object.keys(emptySupplier).map((key) => [key, supplier[key] || ''])))
    setError('')
    setSuccess('')
    setFormOpen(true)
  }

  const saveSupplier = async (event) => {
    event.preventDefault()
    if (saving) return
    setSaving(true)
    setError('')
    setSuccess('')
    const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value.trim() || null]))
    payload.supplier_code = form.supplier_code.trim().toUpperCase()
    payload.supplier_name = form.supplier_name.trim()
    try {
      if (editingId) {
        await supplierService.update(editingId, payload)
        setSuccess('Supplier details updated.')
      } else {
        await supplierService.create(payload)
        setSuccess('Supplier created.')
        setOffset(0)
      }
      setFormOpen(false)
      await loadSuppliers(editingId ? offset : 0)
    } catch (failure) {
      setError(failure.message || 'Could not save the supplier.')
    } finally {
      setSaving(false)
    }
  }

  const toggleStatus = async (supplier) => {
    const nextStatus = supplier.supplier_status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
    if (!window.confirm(`Are you sure you want to ${nextStatus === 'ACTIVE' ? 'activate' : 'deactivate'} ${supplier.supplier_name}?`)) return
    setError('')
    setSuccess('')
    try {
      await supplierService.setStatus(supplier.supplier_id, nextStatus)
      setSuccess(`${supplier.supplier_name} is now ${nextStatus.toLowerCase()}.`)
      await loadSuppliers()
    } catch (failure) {
      setError(failure.message || 'Could not update supplier status.')
    }
  }

  const openDetails = async (supplierId) => {
    setDetails(null)
    setDetailsLoading(true)
    try {
      setDetails(await supplierService.get(supplierId))
    } catch (failure) {
      setError(failure.message || 'Could not load supplier details.')
    } finally {
      setDetailsLoading(false)
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
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Suppliers</h1>
          <p className="mt-2 text-sm text-slate-500">Manage the suppliers serving your company.</p>
        </div>
        {canCreate && <button type="button" onClick={openCreate} className="inline-flex items-center justify-center gap-2 rounded-xl bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-800"><Plus size={17} /> Add supplier</button>}
      </div>

      {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      {success && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{success}</p>}

      {formOpen && <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="mb-5 flex items-start justify-between gap-4"><div><h2 className="font-semibold">{editingId ? 'Edit supplier' : 'Add supplier'}</h2><p className="mt-1 text-sm text-slate-500">This supplier is saved to your company only.</p></div><button type="button" aria-label="Close supplier form" onClick={() => setFormOpen(false)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button></div>
        <form onSubmit={saveSupplier}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {fields.map(([name, label, props]) => <label key={name} className="text-sm font-medium text-slate-700">{label}{props.required ? ' *' : ''}<input {...props} required={props.required} value={form[name]} onChange={(event) => setForm((current) => ({ ...current, [name]: event.target.value }))} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>)}
            <label className="text-sm font-medium text-slate-700 sm:col-span-2 lg:col-span-3">Address<textarea rows={2} maxLength={400} value={form.address} onChange={(event) => setForm((current) => ({ ...current, address: event.target.value }))} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
            <label className="text-sm font-medium text-slate-700 sm:col-span-2 lg:col-span-3">Internal notes<textarea rows={2} maxLength={1000} value={form.notes} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
          </div>
          <div className="mt-5 flex justify-end gap-3"><button type="button" onClick={() => setFormOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button><button disabled={saving} className="rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:opacity-50">{saving ? 'Saving…' : editingId ? 'Save changes' : 'Create supplier'}</button></div>
        </form>
      </div>}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-sky-700"><Truck size={20} /></span><div><h2 className="font-semibold">Company suppliers</h2><p className="text-xs text-slate-500">{total} supplier{total === 1 ? '' : 's'}</p></div></div>
          <div className="flex flex-col gap-2 sm:flex-row"><form onSubmit={submitSearch} className="flex gap-2"><label htmlFor="supplier-search" className="sr-only">Search suppliers</label><input id="supplier-search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search code, name, contact" className="min-w-0 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500" /><button aria-label="Search suppliers" className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50"><Search size={16} /></button></form><label htmlFor="supplier-status-filter" className="sr-only">Filter by supplier status</label><select id="supplier-status-filter" value={statusFilter} onChange={(event) => { setOffset(0); setStatusFilter(event.target.value) }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">All statuses</option><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></select></div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[850px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3 font-semibold">Supplier code</th><th className="px-5 py-3 font-semibold">Supplier</th><th className="px-5 py-3 font-semibold">Contact person</th><th className="px-5 py-3 font-semibold">Phone</th><th className="px-5 py-3 font-semibold">Email</th><th className="px-5 py-3 font-semibold">Status</th><th className="px-5 py-3 text-right font-semibold">Actions</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {suppliers.map((supplier) => <tr key={supplier.supplier_id}>
                <td className="px-5 py-4 font-mono text-xs text-slate-600">{supplier.supplier_code}</td><td className="px-5 py-4 font-semibold text-slate-800">{supplier.supplier_name}</td><td className="px-5 py-4 text-slate-600">{display(supplier.contact_person)}</td><td className="px-5 py-4 text-slate-600">{display(supplier.phone)}</td><td className="px-5 py-4 text-slate-600">{display(supplier.email)}</td><td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${supplier.supplier_status === 'ACTIVE' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>{supplier.supplier_status}</span></td>
                <td className="px-5 py-4"><div className="flex justify-end gap-2"><button type="button" onClick={() => openDetails(supplier.supplier_id)} aria-label={`View ${supplier.supplier_name}`} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium hover:bg-slate-50"><Eye size={14} /> View</button>{canUpdate && <button type="button" onClick={() => openEdit(supplier)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium hover:bg-slate-50"><Pencil size={14} /> Edit</button>}{canChangeStatus && <button type="button" onClick={() => toggleStatus(supplier)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium hover:bg-slate-50"><Power size={14} />{supplier.supplier_status === 'ACTIVE' ? 'Deactivate' : 'Activate'}</button>}</div></td>
              </tr>)}
              {!loading && suppliers.length === 0 && <tr><td colSpan={7} className="px-5 py-14 text-center"><Building2 className="mx-auto text-slate-300" size={28} /><p className="mt-3 font-medium text-slate-700">No suppliers found</p><p className="mt-1 text-sm text-slate-500">Add a supplier to start this company’s supplier directory.</p></td></tr>}
              {loading && <tr><td colSpan={7} className="px-5 py-12 text-center text-sm text-slate-500" role="status">Loading suppliers…</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-500 sm:px-5"><span>{total === 0 ? '0 suppliers' : `${offset + 1}–${Math.min(offset + suppliers.length, total)} of ${total}`}</span><div className="flex gap-2"><button type="button" aria-label="Previous page" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - limit))} className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"><ChevronLeft size={16} /></button><button type="button" aria-label="Next page" disabled={offset + limit >= total || loading} onClick={() => setOffset(offset + limit)} className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"><ChevronRight size={16} /></button></div></div>
      </div>

      {(details || detailsLoading) && <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-900/40 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setDetails(null) }}><section role="dialog" aria-modal="true" aria-labelledby="supplier-detail-title" className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl sm:p-7"><div className="flex items-start justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-sky-700">Supplier details</p><h2 id="supplier-detail-title" className="mt-1 text-xl font-semibold">{details?.supplier_name || 'Loading supplier…'}</h2></div><button type="button" aria-label="Close supplier details" onClick={() => setDetails(null)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button></div>{detailsLoading ? <p role="status" className="py-10 text-center text-sm text-slate-500">Loading details…</p> : details && <><dl className="mt-6 grid gap-x-6 gap-y-4 sm:grid-cols-2">{[['Supplier code', details.supplier_code], ['Status', details.supplier_status], ['Contact person', details.contact_person], ['Email', details.email], ['Phone', details.phone], ['Alternate phone', details.alternate_phone], ['City', details.city], ['Country', details.country], ['Tax registration number', details.tax_registration_number], ['Payment terms', details.payment_terms], ['Address', details.address], ['Internal notes', details.notes]].map(([label, value]) => <div key={label}><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{display(value)}</dd></div>)}</dl><div className="mt-6 rounded-xl border border-dashed border-slate-200 bg-slate-50 p-4"><h3 className="text-sm font-semibold text-slate-700">Purchasing history</h3><p className="mt-1 text-sm text-slate-500">Purchase history will be available when purchase orders are introduced.</p></div></>}</section></div>}
    </section>
  )
}
