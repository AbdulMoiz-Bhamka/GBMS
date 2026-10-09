// src/pages/Dashboard/Dashboard.jsx
import { useEffect, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { useAuth } from '../../auth/useAuth'
import { authService } from '../../services/authService'

export default function DashboardPage() {
  const { token, user } = useAuth()
  const [dashboard, setDashboard] = useState(null)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let active = true
    authService.dashboard(token)
      .then((data) => { if (active) setDashboard(data) })
      .catch((failure) => { if (active) setError(failure.message) })
      .finally(() => { if (active) setIsLoading(false) })
    return () => { active = false }
  }, [token])

  return (
    <section className="text-slate-800">
      <p className="text-sm font-semibold uppercase tracking-wider text-sky-700">Secure workspace</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
        Welcome, {user?.full_name || user?.username || 'Administrator'}
      </h1>
      <p className="mt-2 text-slate-500">Your GBMS business workspace.</p>

      {isLoading && <p className="mt-8 text-sm text-slate-500" role="status">Loading your workspace…</p>}
      {error && <p role="alert" className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{error}</p>}

      {dashboard && (
        <div className="mt-8 grid gap-5 sm:grid-cols-2">
          <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <ShieldCheck className="text-sky-600" aria-hidden="true" />
            <h2 className="mt-4 font-semibold">Account access</h2>
            <p className="mt-1 text-sm text-slate-500">{dashboard.message}</p>
          </article>
          <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm text-slate-500">Signed in as</p>
            <p className="mt-2 text-lg font-semibold">{user?.username}</p>
            <p className="mt-1 text-sm text-slate-500">Role: {user?.role_name || '—'}</p>
          </article>
        </div>
      )}
    </section>
  )
}
