import { useCallback, useEffect, useState } from 'react'
import { Building2, Check, ChevronLeft, ChevronRight, Pencil, Plus, Power, UserRound, X } from 'lucide-react'
import { companyService } from '../../services/companyService'

const emptyCompany = { company_name: '', company_code: '', email: '', phone: '', address: '' }

function displayDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString()
}

export default function CompaniesPage() {
  const [companies, setCompanies] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyCompany)
  const [saving, setSaving] = useState(false)
  const [userCompany, setUserCompany] = useState(null)
  const [companyUsers, setCompanyUsers] = useState([])
  const [userForm, setUserForm] = useState({ username: '', full_name: '', email: '', password: '', role_name: 'COMPANY_ADMIN' })
  const [userSaving, setUserSaving] = useState(false)
  const limit = 20

  const loadCompanies = useCallback(async (requestedOffset = offset) => {
    try {
      const result = await companyService.list({ search, limit, offset: requestedOffset })
      setCompanies(result.items)
      setTotal(result.total)
      setError('')
    } catch (failure) {
      setError(failure.message || 'Could not load companies.')
    } finally {
      setLoading(false)
    }
  }, [search, offset])

  useEffect(() => {
    let active = true
    companyService.list({ search, limit, offset }).then((result) => {
      if (!active) return
      setCompanies(result.items)
      setTotal(result.total)
      setError('')
    }).catch((failure) => {
      if (active) setError(failure.message || 'Could not load companies.')
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [search, offset])

  const openCreate = () => {
    setEditingId(null)
    setForm(emptyCompany)
    setError('')
    setSuccess('')
    setFormOpen(true)
  }

  const openEdit = async (companyId) => {
    setError('')
    setSuccess('')
    try {
      const company = await companyService.get(companyId)
      setEditingId(companyId)
      setForm({
        company_name: company.company_name,
        company_code: company.company_code,
        email: company.email || '',
        phone: company.phone || '',
        address: company.address || '',
      })
      setFormOpen(true)
    } catch (failure) {
      setError(failure.message || 'Could not load company details.')
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    const payload = {
      ...form,
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      address: form.address.trim() || null,
    }
    try {
      if (editingId) {
        await companyService.update(editingId, payload)
        setSuccess('Company details updated.')
      } else {
        await companyService.create(payload)
        setSuccess('Company created.')
        setOffset(0)
      }
      setFormOpen(false)
      await loadCompanies(editingId ? offset : 0)
    } catch (failure) {
      setError(failure.message || 'Could not save company details.')
    } finally {
      setSaving(false)
    }
  }

  const toggleStatus = async (company) => {
    const nextStatus = company.company_status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
    const action = nextStatus === 'ACTIVE' ? 'reactivate' : 'deactivate'
    if (!window.confirm(`Are you sure you want to ${action} ${company.company_name}?`)) return
    setError('')
    setSuccess('')
    try {
      await companyService.setStatus(company.company_id, nextStatus)
      setSuccess(`${company.company_name} is now ${nextStatus.toLowerCase()}.`)
      await loadCompanies()
    } catch (failure) {
      setError(failure.message || 'Could not update company status.')
    }
  }

  const manageUsers = async (company) => {
    setError('')
    setSuccess('')
    setUserCompany(company)
    setCompanyUsers([])
    setUserForm({ username: '', full_name: '', email: '', password: '', role_name: 'COMPANY_ADMIN' })
    try {
      const result = await companyService.users(company.company_id)
      setCompanyUsers(result.items)
    } catch (failure) {
      setError(failure.message || 'Could not load company users.')
    }
  }

  const createCompanyUser = async (event) => {
    event.preventDefault()
    setUserSaving(true)
    setError('')
    try {
      await companyService.createUser(userCompany.company_id, userForm)
      const result = await companyService.users(userCompany.company_id)
      setCompanyUsers(result.items)
      setUserForm({ username: '', full_name: '', email: '', password: '', role_name: 'COMPANY_ADMIN' })
      setSuccess(`Login account created for ${userCompany.company_name}. Share the username and temporary password securely.`)
    } catch (failure) {
      setError(failure.message || 'Could not create company user.')
    } finally {
      setUserSaving(false)
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
          <p className="text-sm font-semibold uppercase tracking-wider text-sky-700">Platform administration</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Company management</h1>
          <p className="mt-2 text-sm text-slate-500">Register and manage independent GBMS company workspaces.</p>
        </div>
        <button type="button" onClick={openCreate} className="inline-flex items-center justify-center gap-2 rounded-xl bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-800 focus:outline-none focus:ring-2 focus:ring-sky-300">
          <Plus size={17} /> Create company
        </button>
      </div>

      {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      {success && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{success}</p>}

      {userCompany && <div className="rounded-2xl border border-sky-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="mb-5 flex items-start justify-between gap-4"><div><p className="text-sm font-semibold uppercase tracking-wider text-sky-700">{userCompany.company_name}</p><h2 className="mt-1 text-lg font-semibold">Company login accounts</h2><p className="mt-1 text-sm text-slate-500">Create the first COMPANY_ADMIN account, then add other roles as needed.</p></div><button type="button" aria-label="Close account management" onClick={() => setUserCompany(null)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button></div>
        <form onSubmit={createCompanyUser} className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <label className="text-sm font-medium text-slate-700">Full name *<input required maxLength={160} value={userForm.full_name} onChange={(e) => setUserForm({ ...userForm, full_name: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal" /></label>
          <label className="text-sm font-medium text-slate-700">Username *<input required minLength={3} maxLength={80} pattern="[A-Za-z0-9_.\-]+" value={userForm.username} onChange={(e) => setUserForm({ ...userForm, username: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal" /></label>
          <label className="text-sm font-medium text-slate-700">Email *<input required type="email" maxLength={254} value={userForm.email} onChange={(e) => setUserForm({ ...userForm, email: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal" /></label>
          <label className="text-sm font-medium text-slate-700">Temporary password *<input required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={userForm.password} onChange={(e) => setUserForm({ ...userForm, password: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal" /><span className="text-xs font-normal text-slate-500">At least 12 characters.</span></label>
          <label className="text-sm font-medium text-slate-700">Role<select value={userForm.role_name} onChange={(e) => setUserForm({ ...userForm, role_name: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal"><option value="COMPANY_ADMIN">Company Admin</option><option value="SUB_ADMIN">Sub Admin</option><option value="INVENTORY_USER">Inventory User</option></select></label>
          <div className="flex items-end"><button disabled={userSaving || userCompany.company_status !== 'ACTIVE'} className="inline-flex items-center gap-2 rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:opacity-50"><UserRound size={16} />{userSaving ? 'Creating…' : 'Create login account'}</button></div>
        </form>
        <div className="mt-5 overflow-x-auto rounded-xl border border-slate-200"><table className="w-full min-w-[620px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-4 py-2">Person</th><th className="px-4 py-2">Username</th><th className="px-4 py-2">Role</th><th className="px-4 py-2">Status</th></tr></thead><tbody className="divide-y divide-slate-100">{companyUsers.map((user) => <tr key={user.user_id}><td className="px-4 py-3">{user.full_name}<span className="block text-xs text-slate-500">{user.email}</span></td><td className="px-4 py-3 font-mono text-xs">{user.username}</td><td className="px-4 py-3">{user.role_name.replaceAll('_', ' ')}</td><td className="px-4 py-3">{user.account_status}</td></tr>)}{companyUsers.length === 0 && <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-500">No accounts yet. Create the company administrator above.</td></tr>}</tbody></table></div>
        <p className="mt-3 text-xs text-slate-500">The new user signs in through the existing GBMS login screen. Company data access is limited to this company.</p>
      </div>}

      {formOpen && (
        <form onSubmit={handleSubmit} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div><h2 className="font-semibold">{editingId ? 'Edit company' : 'Create company'}</h2><p className="mt-1 text-sm text-slate-500">Company code must be unique and stable.</p></div>
            <button type="button" aria-label="Close company form" onClick={() => setFormOpen(false)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">Company name *<input required maxLength={160} value={form.company_name} onChange={(event) => setForm({ ...form, company_name: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
            <label className="text-sm font-medium text-slate-700">Company code *<input required minLength={2} maxLength={30} pattern="[A-Za-z0-9][A-Za-z0-9_\-]{1,29}" value={form.company_code} onChange={(event) => setForm({ ...form, company_code: event.target.value.toUpperCase() })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal uppercase outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /><span className="mt-1 block text-xs font-normal text-slate-500">Letters, numbers, underscores, or hyphens.</span></label>
            <label className="text-sm font-medium text-slate-700">Contact email<input type="email" maxLength={254} value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
            <label className="text-sm font-medium text-slate-700">Phone<input maxLength={40} value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
            <label className="text-sm font-medium text-slate-700 sm:col-span-2">Address<textarea rows={2} maxLength={400} value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
          </div>
          <div className="mt-5 flex flex-wrap justify-end gap-3">
            <button type="button" onClick={() => setFormOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
            <button disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:opacity-60"><Check size={16} />{saving ? 'Saving…' : editingId ? 'Save changes' : 'Create company'}</button>
          </div>
        </form>
      )}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-sky-700"><Building2 size={20} /></span><div><h2 className="font-semibold">Registered companies</h2><p className="text-xs text-slate-500">{total} total</p></div></div>
          <form onSubmit={submitSearch} className="flex gap-2"><label className="sr-only" htmlFor="company-search">Search companies</label><input id="company-search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search name or code" className="min-w-0 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500" /><button className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50">Search</button></form>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3 font-semibold">Company</th><th className="px-5 py-3 font-semibold">Code</th><th className="px-5 py-3 font-semibold">Contact</th><th className="px-5 py-3 font-semibold">Status</th><th className="px-5 py-3 font-semibold">Created</th><th className="px-5 py-3 text-right font-semibold">Actions</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {companies.map((company) => <tr key={company.company_id}>
                <td className="px-5 py-4"><span className="font-semibold text-slate-800">{company.company_name}</span>{company.address && <span className="mt-1 block max-w-56 truncate text-xs text-slate-500">{company.address}</span>}</td>
                <td className="px-5 py-4 font-mono text-xs text-slate-600">{company.company_code}</td>
                <td className="px-5 py-4 text-slate-600">{company.email || '—'}{company.phone && <span className="mt-1 block text-xs text-slate-500">{company.phone}</span>}</td>
                <td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${company.company_status === 'ACTIVE' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>{company.company_status}</span></td>
                <td className="px-5 py-4 text-slate-500">{displayDate(company.created_at)}</td>
                <td className="px-5 py-4"><div className="flex justify-end gap-2"><button type="button" onClick={() => manageUsers(company)} className="inline-flex items-center gap-1.5 rounded-lg border border-sky-200 px-2.5 py-1.5 text-xs font-medium text-sky-700 hover:bg-sky-50"><UserRound size={14} /> Accounts</button><button type="button" onClick={() => openEdit(company.company_id)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium hover:bg-slate-50"><Pencil size={14} /> Edit</button><button type="button" onClick={() => toggleStatus(company)} className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium ${company.company_status === 'ACTIVE' ? 'border-rose-200 text-rose-700 hover:bg-rose-50' : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'}`}><Power size={14} />{company.company_status === 'ACTIVE' ? 'Deactivate' : 'Activate'}</button></div></td>
              </tr>)}
              {!loading && companies.length === 0 && <tr><td colSpan={6} className="px-5 py-14 text-center"><Building2 className="mx-auto text-slate-300" size={28} /><p className="mt-3 font-medium text-slate-700">No companies found</p><p className="mt-1 text-sm text-slate-500">Create a company workspace to get started.</p></td></tr>}
              {loading && <tr><td colSpan={6} className="px-5 py-12 text-center text-sm text-slate-500" role="status">Loading companies…</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-500 sm:px-5">
          <span>{total === 0 ? '0 companies' : `${offset + 1}–${Math.min(offset + companies.length, total)} of ${total}`}</span>
          <div className="flex gap-2"><button type="button" aria-label="Previous page" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - limit))} className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"><ChevronLeft size={16} /></button><button type="button" aria-label="Next page" disabled={offset + limit >= total || loading} onClick={() => setOffset(offset + limit)} className="rounded-lg border border-slate-200 p-2 disabled:opacity-40"><ChevronRight size={16} /></button></div>
        </div>
      </div>
    </section>
  )
}
