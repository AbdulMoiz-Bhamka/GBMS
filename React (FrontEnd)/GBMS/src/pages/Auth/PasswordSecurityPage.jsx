import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, KeyRound, LoaderCircle, LogOut } from 'lucide-react'
import { useAuth } from '../../auth/useAuth'
import { authService } from '../../services/authService'

export default function PasswordSecurityPage({ forced = false }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (form.new_password.length < 12 || !/[A-Za-z]/.test(form.new_password) || !/\d/.test(form.new_password)) {
      setError('Use at least 12 characters with a letter and a number.')
      return
    }
    if (form.new_password !== form.confirm_password) {
      setError('The new password and confirmation do not match.')
      return
    }
    setSaving(true)
    try {
      await authService.changePassword(form)
      // The password update increments the token version, so this token cannot be reused.
      window.alert('Password changed successfully. Sign in again with your new password.')
      logout()
      navigate('/', { replace: true })
    } catch (failure) {
      setError(failure.message || 'Could not change your password.')
    } finally {
      setSaving(false)
    }
  }

  return <main className="grid min-h-[70vh] place-items-center p-4 text-slate-800">
    <section className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="mb-6 flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-sky-50 text-sky-700"><KeyRound size={21} /></span><div><p className="text-xs font-semibold uppercase tracking-wider text-sky-700">{forced ? 'Action required' : 'Account security'}</p><h1 className="mt-1 text-xl font-semibold">{forced ? 'Set a new password' : 'Change password'}</h1></div></div>
      <p className="mb-5 text-sm text-slate-500">{forced ? 'Your administrator gave you a temporary password. Choose a new one to continue to GBMS.' : `Update the password for ${user?.username || 'your account'}.`}</p>
      {error && <p role="alert" className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      <form onSubmit={submit} className="space-y-4">
        <label className="block text-sm font-medium">{forced ? 'Temporary password' : 'Current password'}<input required type="password" autoComplete="current-password" value={form.current_password} onChange={(event) => setForm({ ...form, current_password: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
        <label className="block text-sm font-medium">New password<input required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={form.new_password} onChange={(event) => setForm({ ...form, new_password: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /><span className="mt-1 block text-xs font-normal text-slate-500">At least 12 characters, including a letter and a number.</span></label>
        <label className="block text-sm font-medium">Confirm new password<input required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={form.confirm_password} onChange={(event) => setForm({ ...form, confirm_password: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
        <button type="submit" disabled={saving} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-sky-700 px-4 py-2.5 font-semibold text-white hover:bg-sky-800 disabled:opacity-60">{saving ? <LoaderCircle size={17} className="animate-spin" /> : <Check size={17} />}{saving ? 'Updating…' : 'Update password'}</button>
      </form>
      {!forced && <button type="button" onClick={() => { logout(); navigate('/', { replace: true }) }} className="mt-4 inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-800"><LogOut size={15} /> Sign out</button>}
    </section>
  </main>
}
