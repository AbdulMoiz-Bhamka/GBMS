import { useCallback, useEffect, useState } from 'react'
import { Check, Clipboard, KeyRound, LoaderCircle, Pencil, Plus, Power, Search, ShieldCheck, Trash2, UserRound, Users, X } from 'lucide-react'
import { useAuth } from '../../auth/useAuth'
import { usersService } from '../../services/usersService'

const blankForm = () => ({
  username: '', full_name: '', email: '', password: '', role_name: 'INVENTORY_USER', permission_codes: ['inventory.view'],
})

export default function UsersPage() {
  const { user } = useAuth()
  const companyId = user?.company_id
  const canAssignRoles = user?.permissions?.includes('users.assign_role')
  const canCreateUsers = user?.permissions?.includes('users.create') && canAssignRoles
  const canEditUsers = user?.permissions?.includes('users.update')
  const canChangeStatus = user?.permissions?.includes('users.deactivate')
  const canDeleteUsers = user?.permissions?.includes('users.delete')
  const [users, setUsers] = useState([])
  const [options, setOptions] = useState({ roles: [], permissions: [] })
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [resetCredential, setResetCredential] = useState(null)
  const [resettingUserId, setResettingUserId] = useState(null)
  const [form, setForm] = useState(blankForm)
  const canEditAccess = canAssignRoles
    && (!editingUser || editingUser.user_id !== user?.user_id)

  const loadUsers = useCallback(async () => {
    if (!companyId) return
    setLoading(true)
    try {
      const result = await usersService.list(companyId, search)
      setUsers(result.items || [])
      setError('')
    } catch (failure) {
      setError(failure.message || 'Could not load company users.')
    } finally {
      setLoading(false)
    }
  }, [companyId, search])

  useEffect(() => {
    let active = true
    Promise.all([
      usersService.list(companyId, search),
      canAssignRoles ? usersService.options() : Promise.resolve({ roles: [], permissions: [] }),
    ])
      .then(([result, assignable]) => {
        if (!active) return
        setUsers(result.items || [])
        setOptions(assignable)
        setError('')
      })
      .catch((failure) => { if (active) setError(failure.message || 'Could not load user management.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [companyId, search, canAssignRoles])

  const openCreate = () => {
    setEditingUser(null)
    setForm(blankForm())
    setError('')
    setSuccess('')
    setFormOpen(true)
  }

  const openEdit = (account) => {
    setEditingUser(account)
    setForm({
      username: account.username,
      full_name: account.full_name,
      email: account.email,
      password: '',
      role_name: account.role_name,
      permission_codes: account.permission_codes || [],
    })
    setError('')
    setSuccess('')
    setFormOpen(true)
  }

  const togglePermission = (code) => {
    setForm((current) => ({
      ...current,
      permission_codes: current.permission_codes.includes(code)
        ? current.permission_codes.filter((item) => item !== code)
        : [...current.permission_codes, code],
    }))
  }

  const saveUser = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    const payload = {
      username: form.username.trim(),
      full_name: form.full_name.trim(),
      email: form.email.trim(),
    }
    if (canEditAccess && (user?.user_id !== editingUser?.user_id)) {
      payload.role_name = form.role_name
      payload.permission_codes = form.role_name === 'WORKER' ? [] : form.permission_codes
    }
    if (!editingUser) {
      payload.password = form.password
      payload.role_name = form.role_name
        payload.permission_codes = form.role_name === 'WORKER' ? [] : form.permission_codes
    }
    try {
      if (editingUser) {
        await usersService.update(companyId, editingUser.user_id, payload)
        setSuccess('User details and permissions updated.')
      } else {
        await usersService.create(companyId, payload)
        setSuccess('Company user created. They can now sign in with their username and password.')
      }
      setFormOpen(false)
      await loadUsers()
    } catch (failure) {
      setError(failure.message || 'Could not save this user.')
    } finally {
      setSaving(false)
    }
  }

  const toggleStatus = async (account) => {
    const nextStatus = account.account_status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
    const verb = nextStatus === 'ACTIVE' ? 'reactivate' : 'deactivate'
    if (!window.confirm(`Are you sure you want to ${verb} ${account.full_name}? Their current session will stop working after the change.`)) return
    setError('')
    setSuccess('')
    try {
      await usersService.setStatus(companyId, account.user_id, nextStatus)
      setSuccess(`${account.full_name} is now ${nextStatus.toLowerCase()}.`)
      await loadUsers()
    } catch (failure) {
      setError(failure.message || 'Could not update account status.')
    }
  }

  const deleteUser = async (account) => {
    const confirmed = window.confirm(
      `Permanently delete ${account.full_name} (${account.username})? They will lose access immediately, and the username and email can be reused. This cannot be undone.`,
    )
    if (!confirmed) return
    setError('')
    setSuccess('')
    try {
      await usersService.delete(companyId, account.user_id)
      setSuccess(`${account.full_name} was permanently deleted. Their username and email are available again.`)
      await loadUsers()
    } catch (failure) {
      setError(failure.message || 'Could not delete this user.')
    }
  }

  const resetPassword = async (account) => {
    if (!window.confirm(`Create a one-time temporary password for ${account.full_name}? Their current sessions will be signed out.`)) return
    setError('')
    setSuccess('')
    setResettingUserId(account.user_id)
    try {
      const result = await usersService.resetPassword(companyId, account.user_id)
      setResetCredential(result)
      setSuccess(`Temporary password created for ${account.username}. Share it privately; it is shown only once.`)
    } catch (failure) {
      setError(failure.message || 'Could not reset this password.')
    } finally {
      setResettingUserId(null)
    }
  }

  return (
    <section className="space-y-6 text-slate-800">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-sky-700">Company workspace</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Team and access</h1>
          <p className="mt-2 text-slate-500">Create accounts for your team and choose what each person can access.</p>
        </div>
        {canCreateUsers && <button type="button" onClick={openCreate} className="inline-flex items-center justify-center gap-2 rounded-lg bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-800">
          <Plus size={17} /> Create user
        </button>}
      </header>

      {error && !formOpen && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
      {success && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{success}</p>}

      {resetCredential && <div role="dialog" aria-modal="true" aria-labelledby="reset-password-title" className="fixed inset-0 z-[80] grid place-items-center bg-slate-950/40 p-4">
        <section className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-sky-50 text-sky-700"><KeyRound size={19} /></span><div><h2 id="reset-password-title" className="font-semibold">Temporary password</h2><p className="text-xs text-slate-500">For {resetCredential.username}</p></div></div>
          <p className="mt-4 text-sm text-slate-600">Give this password to the user privately. They must choose a new password at next sign-in. This value will not be shown again.</p>
          <code className="mt-3 block break-all rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">{resetCredential.temporary_password}</code>
          <div className="mt-5 flex justify-end gap-2"><button type="button" onClick={async () => { try { await navigator.clipboard.writeText(resetCredential.temporary_password) } catch { setError('Clipboard access failed. Select and copy the password manually.') } }} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm"><Clipboard size={15} /> Copy</button><button type="button" onClick={() => setResetCredential(null)} className="rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white">Done</button></div>
        </section>
      </div>}

      {formOpen && <div className="fixed inset-0 z-[70] grid place-items-center overflow-y-auto bg-slate-950/40 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving) setFormOpen(false) }}>
        <section role="dialog" aria-modal="true" aria-labelledby="user-form-title" className="my-auto max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div className="flex items-start justify-between border-b border-slate-100 px-6 py-5">
            <div><p className="text-xs font-semibold uppercase tracking-wider text-sky-700">Company user</p><h2 id="user-form-title" className="mt-1 text-xl font-semibold">{editingUser ? 'Edit user access' : 'Create a user account'}</h2><p className="mt-1 text-sm text-slate-500">Access is limited to this company and the permissions selected below.</p></div>
            <button type="button" aria-label="Close form" disabled={saving} onClick={() => setFormOpen(false)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={18} /></button>
          </div>
          <form onSubmit={saveUser} className="space-y-5 p-6">
            {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-medium">Full name<input required maxLength={160} value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
              <label className="text-sm font-medium">Username<input required minLength={3} maxLength={80} pattern="[A-Za-z0-9_.-]+" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
              <label className="text-sm font-medium">Email<input required type="email" maxLength={254} value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
              {!editingUser && <label className="text-sm font-medium">Temporary password<input required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /><span className="mt-1 block text-xs font-normal text-slate-500">At least 12 characters. Share it securely with the user.</span></label>}
              {canEditAccess && <label className="text-sm font-medium">Role<select value={form.role_name} onChange={(event) => { const roleName = event.target.value; setForm({ ...form, role_name: roleName, permission_codes: roleName === 'WORKER' ? [] : form.permission_codes }) }} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100">{options.roles.map((role) => <option key={role} value={role}>{role === 'WORKER' ? 'Worker' : role.replaceAll('_', ' ')}</option>)}</select></label>}
            </div>
            {canEditAccess && form.role_name === 'WORKER' && <p className="rounded-lg border border-sky-100 bg-sky-50 p-3 text-sm text-sky-800">Worker accounts can only open their personal dashboard. Attendance, work hours, and salary tracking will be added later.</p>}
            {canEditAccess && form.role_name !== 'WORKER' && <fieldset>
              <legend className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck size={17} className="text-sky-700" /> Permissions</legend>
              <p className="mt-1 text-xs text-slate-500">Choose only the work this user needs. The dashboard and navigation follow these permissions.</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {options.permissions.map(({ code, label }) => <label key={code} className="flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 px-3 py-2.5 text-sm hover:bg-slate-50"><input type="checkbox" checked={form.permission_codes.includes(code)} onChange={() => togglePermission(code)} className="checkbox checkbox-sm checkbox-primary" /><span>{label}</span><code className="ml-auto hidden text-[10px] text-slate-400 lg:block">{code}</code></label>)}
              </div>
            </fieldset>}
            <div className="flex justify-end gap-3 border-t border-slate-100 pt-4"><button type="button" disabled={saving} onClick={() => setFormOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button><button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:opacity-60">{saving ? <LoaderCircle size={16} className="animate-spin" /> : <Check size={16} />}{saving ? 'Saving…' : editingUser ? 'Save changes' : 'Create account'}</button></div>
          </form>
        </section>
      </div>}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-sky-50 text-sky-700"><Users size={19} /></span><div><h2 className="font-semibold">Company users</h2><p className="text-xs text-slate-500">{users.length} account{users.length === 1 ? '' : 's'}</p></div></div>
          <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); if (searchInput.trim() === search) loadUsers(); else { setLoading(true); setSearch(searchInput) } }}><label className="sr-only" htmlFor="user-search">Search users</label><input id="user-search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search name, username, email" className="min-w-0 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500" /><button className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50"><Search size={15} /> Search</button></form>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[940px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Person</th><th className="px-5 py-3">Username</th><th className="px-5 py-3">Role</th><th className="px-5 py-3">Permissions</th><th className="px-5 py-3">Status</th><th className="px-5 py-3 text-right">Actions</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {loading && <tr><td colSpan={6} className="px-5 py-12 text-center text-slate-500" role="status">Loading company users…</td></tr>}
              {!loading && users.map((account) => <tr key={account.user_id}>
                <td className="px-5 py-4"><div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-full bg-slate-100 text-slate-600"><UserRound size={16} /></span><span><strong className="block font-medium">{account.full_name}</strong><small className="text-slate-500">{account.email}</small></span></div></td>
                <td className="px-5 py-4 font-mono text-xs">{account.username}</td>
                <td className="px-5 py-4">{account.role_name.replaceAll('_', ' ')}</td>
                <td className="px-5 py-4"><span className="text-xs text-slate-600">{(account.permission_codes || []).length} granted</span><div className="mt-1 flex max-w-xs flex-wrap gap-1">{(account.permission_codes || []).slice(0, 3).map((code) => <span key={code} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">{code}</span>)}{(account.permission_codes || []).length > 3 && <span className="text-[10px] text-slate-400">+{account.permission_codes.length - 3}</span>}</div></td>
                <td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${account.account_status === 'ACTIVE' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>{account.account_status}</span></td>
                <td className="px-5 py-4"><div className="flex justify-end gap-2">{canEditUsers && <button type="button" onClick={() => openEdit(account)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-medium hover:bg-slate-50"><Pencil size={14} /> Edit</button>}{canEditUsers && account.user_id !== user?.user_id && <button type="button" disabled={resettingUserId === account.user_id} onClick={() => resetPassword(account)} className="inline-flex items-center gap-1.5 rounded-lg border border-amber-200 px-2.5 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-50 disabled:opacity-50"><KeyRound size={14} />{resettingUserId === account.user_id ? 'Resetting…' : 'Reset password'}</button>}{canChangeStatus && account.user_id !== user?.user_id && <button type="button" onClick={() => toggleStatus(account)} className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium ${account.account_status === 'ACTIVE' ? 'border-rose-200 text-rose-700 hover:bg-rose-50' : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'}`}><Power size={14} />{account.account_status === 'ACTIVE' ? 'Deactivate' : 'Activate'}</button>}{canDeleteUsers && account.user_id !== user?.user_id && <button type="button" onClick={() => deleteUser(account)} className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 px-2.5 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-50"><Trash2 size={14} /> Delete</button>}</div></td>
              </tr>)}
              {!loading && users.length === 0 && <tr><td colSpan={6} className="px-5 py-14 text-center"><Users size={26} className="mx-auto text-slate-300" /><p className="mt-3 font-medium text-slate-700">No company users found</p><p className="mt-1 text-sm text-slate-500">Create a user account to give a teammate access to this workspace.</p></td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
