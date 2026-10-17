// src/pages/Dashboard/Dashboard.jsx
import { useEffect, useState } from 'react'
import { ArrowRight, Building2, CalendarCheck2, CircleDollarSign, Clock3, Gauge, Package, ShieldCheck, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import { authService } from '../../services/authService'

export default function DashboardPage() {
  const { token, user } = useAuth()
  const isWorker = user?.role_name === 'WORKER'
  const [dashboard, setDashboard] = useState(null)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const modules = [
    ...(user?.role_name === 'SUPER_ADMIN' ? [{ title: 'Company management', text: 'Create and manage GBMS company workspaces.', path: '/companies', icon: Building2 }] : []),
    ...(user?.company_id != null && user?.permissions?.includes('users.view') ? [{ title: 'Team and access', text: 'Manage your company accounts and assigned permissions.', path: '/users', icon: Users }] : []),
    ...(user?.company_id != null && user?.permissions?.includes('inventory.view') ? [{ title: 'Inventory', text: 'Open the inventory workspace available to your account.', path: '/inventory', icon: Package }] : []),
  ]

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
      <p className="text-sm font-semibold uppercase tracking-wider text-sky-700">{isWorker ? 'Worker workspace' : user?.role_name === 'SUPER_ADMIN' ? 'Platform workspace' : user?.company_id ? 'Company workspace' : 'Secure workspace'}</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
        Welcome, {user?.full_name || user?.username || 'Administrator'}
      </h1>
      <p className="mt-2 text-slate-500">{isWorker ? 'Your personal work and performance overview.' : user?.company_id ? 'Your account is connected to your company workspace.' : 'Your GBMS business workspace.'}</p>

      {isLoading && <p className="mt-8 text-sm text-slate-500" role="status">Loading your workspace…</p>}
      {error && <p role="alert" className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{error}</p>}

      {isWorker && dashboard && <section className="mt-8" aria-labelledby="worker-performance-title">
        <div className="mb-4"><h2 id="worker-performance-title" className="text-lg font-semibold">My performance</h2><p className="mt-1 text-sm text-slate-500">Your attendance, work hours, and pay details will appear here when those features are added.</p></div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            { title: 'Attendance', detail: 'Daily attendance records', icon: CalendarCheck2 },
            { title: 'Hours worked', detail: 'Machine and shift hours', icon: Clock3 },
            { title: 'Salary & pay', detail: 'Your salary information', icon: CircleDollarSign },
            { title: 'Performance', detail: 'Work output and progress', icon: Gauge },
          ].map(({ title, detail, icon: Icon }) => <article key={title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-sky-50 text-sky-700"><Icon size={19} /></span>
            <h3 className="mt-4 font-semibold">{title}</h3>
            <p className="mt-1 text-sm text-slate-500">{detail}</p>
            <span className="mt-4 inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">Coming soon</span>
          </article>)}
        </div>
      </section>}

      {dashboard && !isWorker && (
        <div className="mt-8 grid gap-5 sm:grid-cols-2">
          <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <ShieldCheck className="text-sky-600" aria-hidden="true" />
            <h2 className="mt-4 font-semibold">Account access</h2>
            <p className="mt-1 text-sm text-slate-500">{dashboard.message}</p>
          </article>
          <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm text-slate-500">Signed in as</p>
            <p className="mt-2 text-lg font-semibold">{user?.username}</p>
            <p className="mt-1 text-sm text-slate-500">Role: {user?.role_name?.replaceAll('_', ' ') || '—'}</p>
            {user?.company_id && <p className="mt-1 text-sm text-slate-500">Company workspace #{user.company_id}</p>}
          </article>
        </div>
      )}

      {!isWorker && !isLoading && !error && <section className="mt-8" aria-labelledby="available-modules-title">
        <div className="mb-4"><h2 id="available-modules-title" className="text-lg font-semibold">Your available workspace</h2><p className="mt-1 text-sm text-slate-500">Modules appear here based on your account permissions.</p></div>
        {modules.length ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{modules.map(({ title, text, path, icon: Icon }) => <Link key={path} to={path} className="group flex items-start gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-sky-200 hover:shadow-md"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-sky-50 text-sky-700"><Icon size={20} /></span><span><strong className="block font-semibold text-slate-800">{title}</strong><span className="mt-1 block text-sm text-slate-500">{text}</span><span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-sky-700">Open module <ArrowRight size={13} className="transition group-hover:translate-x-0.5" /></span></span></Link>)}</div> : <p className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600">Your account can view this dashboard. Ask your company administrator if you need access to another module.</p>}
      </section>}
    </section>
  )
}
