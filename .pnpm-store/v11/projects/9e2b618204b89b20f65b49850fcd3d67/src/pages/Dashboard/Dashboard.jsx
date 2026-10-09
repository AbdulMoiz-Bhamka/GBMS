// src/pages/Dashboard/Dashboard.jsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../auth/useAuth'
import { authService } from '../../services/authService'

export default function DashboardPage() {
  const { token, user, logout } = useAuth()
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    authService.dashboard(token).then(setDashboard).catch((failure) => setError(failure.message))
  }, [token])
  const signOut = () => { logout(); navigate('/', { replace: true }) }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <a href="/" className="font-bold tracking-wide text-sky-800">GBMS <span className="font-normal text-slate-500">Workspace</span></a>
        <button onClick={signOut} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium hover:bg-slate-50"><LogOut size={16} /> Sign out</button>
      </div></header>
      <section className="mx-auto max-w-6xl px-6 py-12">
        <p className="text-sm font-semibold uppercase tracking-wider text-sky-700">Secure workspace</p>
        <h1 className="mt-2 text-3xl font-semibold">Welcome, {user?.full_name || user?.username}</h1>
        <p className="mt-2 text-slate-500">Your GBMS account is signed in and ready.</p>
        {error && <p role="alert" className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-800">{error}</p>}
        {dashboard && <div className="mt-8 grid gap-5 sm:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><ShieldCheck className="text-sky-600" /><h2 className="mt-4 font-semibold">Account access</h2><p className="mt-1 text-sm text-slate-500">{dashboard.message}</p></div>
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><p className="text-sm text-slate-500">Signed in as</p><p className="mt-2 text-lg font-semibold">{user?.username}</p><p className="mt-1 text-sm text-slate-500">Role: {user?.role_name}</p></div>
        </div>}
      </section>
    </main>

  )
}
