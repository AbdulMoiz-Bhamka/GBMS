// src/pages/Dashboard/Dashboard.jsx
import { useCallback, useEffect, useState } from 'react'
import {
  ArrowRight, Building2, CalendarCheck2, CircleDollarSign, Clock3,
  Gauge, Package, RefreshCw, ShieldCheck, Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import { authService } from '../../services/authService'
import { dashboardService } from '../../services/dashboardService'

const REFRESH_INTERVAL_MS = 15000

function formatQuantity(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(Number(value || 0))
}

function InventoryChart({ items = [] }) {
  const maxQuantity = Math.max(0, ...items.map((item) => Number(item.quantity || 0)))
  const scale = maxQuantity || 1

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-slate-800">Inventory by product</h2>
          <p className="mt-1 text-sm text-slate-500">Current on-hand quantity for active products</p>
        </div>
        <span className="rounded-lg bg-sky-50 p-2 text-sky-700"><Package size={18} /></span>
      </div>
      {items.length ? <div className="mt-6 overflow-x-auto pb-2">
        <div className="flex min-w-max gap-3">
          <div className="flex h-[230px] w-10 shrink-0 flex-col justify-between pb-7 pt-1 text-right text-[10px] text-slate-400" aria-hidden="true">
            <span>{formatQuantity(maxQuantity)}</span><span>{formatQuantity(maxQuantity / 2)}</span><span>0</span>
          </div>
          <div className="relative flex h-[230px] items-stretch gap-3 border-b border-l border-slate-200 px-3">
            <div className="pointer-events-none absolute inset-x-0 top-0 flex h-[190px] flex-col justify-between" aria-hidden="true">
              <span className="border-t border-dashed border-slate-100" /><span className="border-t border-dashed border-slate-100" /><span className="border-t border-dashed border-slate-100" />
            </div>
            {items.map((item) => {
              const quantity = Number(item.quantity || 0)
              const height = quantity > 0 ? Math.max((quantity / scale) * 82, 2) : 0
              return <div key={item.product_id} className="relative z-10 flex w-[76px] shrink-0 flex-col items-center">
                <div className="relative h-[190px] w-full">
                  <span className="absolute left-1/2 z-20 -translate-x-1/2 whitespace-nowrap text-[10px] font-semibold text-slate-600" style={{ bottom: `calc(${height}% + 5px)` }}>
                    {formatQuantity(quantity)}
                  </span>
                  <div className="absolute bottom-0 left-1/2 w-9 -translate-x-1/2 rounded-t-md bg-sky-500 transition-all" style={{ height: `${height}%` }} title={`${item.product_name}: ${formatQuantity(quantity)} ${item.unit}`} />
                </div>
                <span className="mt-2 w-full truncate text-center text-[10px] text-slate-600" title={item.product_name}>{item.product_name}</span>
                <span className="text-[9px] text-slate-400">{item.unit}</span>
              </div>
            })}
          </div>
        </div>
      </div> : <div className="mt-6 grid min-h-48 place-items-center rounded-xl border border-dashed border-slate-200 text-center">
        <div><Package size={24} className="mx-auto text-slate-300" /><p className="mt-2 text-sm font-medium text-slate-700">No active products yet</p><p className="mt-1 text-xs text-slate-500">Add products and enter their current quantities to see the chart.</p></div>
      </div>}
      <p className="mt-3 text-xs text-slate-400">Each bar shows its own unit, such as pieces, kilograms, or metres.</p>
    </article>
  )
}

function WorkersChart({ workers = { total: 0, active_accounts: 0, inactive_accounts: 0 } }) {
  const total = Number(workers.total || 0)
  const active = Number(workers.active_accounts || 0)
  const inactive = Number(workers.inactive_accounts || 0)
  const activePercent = total ? (active / total) * 100 : 0
  const background = total
    ? `conic-gradient(#0284c7 0 ${activePercent}%, #cbd5e1 ${activePercent}% 100%)`
    : '#e2e8f0'

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div>
        <h2 className="font-semibold text-slate-800">Workers</h2>
        <p className="mt-1 text-sm text-slate-500">Company worker accounts</p>
      </div>
      <div className="mt-7 flex flex-col items-center">
        <div className="grid h-48 w-48 place-items-center rounded-full p-4" style={{ background }} role="img" aria-label={`${active} active worker accounts and ${inactive} inactive worker accounts`}>
          <div className="grid h-full w-full place-items-center rounded-full bg-white text-center">
            <div><strong className="block text-4xl font-semibold text-slate-800">{total}</strong><span className="text-xs text-slate-500">total workers</span></div>
          </div>
        </div>
        <div className="mt-6 grid w-full gap-3">
          <div className="flex items-center justify-between text-sm"><span className="flex items-center gap-2 text-slate-600"><i className="h-3 w-3 rounded-full bg-sky-600" />Active accounts</span><strong>{active}</strong></div>
          <div className="flex items-center justify-between text-sm"><span className="flex items-center gap-2 text-slate-600"><i className="h-3 w-3 rounded-full bg-slate-300" />Inactive accounts</span><strong>{inactive}</strong></div>
        </div>
      </div>
      <p className="mt-5 text-xs leading-5 text-slate-400">Active means the worker can sign in. Attendance tracking is not available yet, so this does not indicate who is on shift today.</p>
    </article>
  )
}

function WorkerPerformance() {
  const cards = [
    { title: 'Attendance', detail: 'Daily attendance records', icon: CalendarCheck2 },
    { title: 'Hours worked', detail: 'Machine and shift hours', icon: Clock3 },
    { title: 'Salary & pay', detail: 'Your salary information', icon: CircleDollarSign },
    { title: 'Performance', detail: 'Work output and progress', icon: Gauge },
  ]
  return <section className="mt-8" aria-labelledby="worker-performance-title">
    <div className="mb-4"><h2 id="worker-performance-title" className="text-lg font-semibold">My performance</h2><p className="mt-1 text-sm text-slate-500">Your personal work summary will grow as factory tracking features are added.</p></div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(({ title, detail, icon: Icon }) => <article key={title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-sky-50 text-sky-700"><Icon size={19} /></span>
      <h3 className="mt-4 font-semibold">{title}</h3><p className="mt-1 text-sm text-slate-500">{detail}</p>
      <span className="mt-4 inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">Coming soon</span>
    </article>)}</div>
  </section>
}

export default function DashboardPage() {
  const { token, user } = useAuth()
  const isWorker = user?.role_name === 'WORKER'
  const canViewCompanyOverview = user?.company_id != null
    && user?.permissions?.includes('dashboard.company_overview')
  const [dashboard, setDashboard] = useState(null)
  const [overview, setOverview] = useState(null)
  const [error, setError] = useState('')
  const [overviewError, setOverviewError] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [overviewLoading, setOverviewLoading] = useState(false)

  const modules = [
    ...(user?.role_name === 'SUPER_ADMIN' ? [{ title: 'Company management', text: 'Create and manage GBMS company workspaces.', path: '/companies', icon: Building2 }] : []),
    ...(user?.company_id != null && user?.permissions?.includes('users.view') ? [{ title: 'Team and access', text: 'Manage your company accounts and assigned permissions.', path: '/users', icon: Users }] : []),
    ...(user?.company_id != null && user?.permissions?.includes('inventory.view') ? [{ title: 'Inventory', text: 'Open the inventory workspace available to your account.', path: '/inventory', icon: Package }] : []),
  ]

  const refreshOverview = useCallback(async () => {
    if (!canViewCompanyOverview) return
    setOverviewLoading(true)
    try {
      const data = await dashboardService.companyOverview()
      setOverview(data)
      setOverviewError('')
    } catch (failure) {
      setOverviewError(failure.message || 'Could not load the company overview.')
    } finally {
      setOverviewLoading(false)
    }
  }, [canViewCompanyOverview])

  useEffect(() => {
    let active = true
    authService.dashboard(token)
      .then((data) => { if (active) setDashboard(data) })
      .catch((failure) => { if (active) setError(failure.message) })
      .finally(() => { if (active) setIsLoading(false) })
    return () => { active = false }
  }, [token])

  useEffect(() => {
    if (!canViewCompanyOverview) return undefined
    refreshOverview()
    const interval = window.setInterval(refreshOverview, REFRESH_INTERVAL_MS)
    return () => window.clearInterval(interval)
  }, [canViewCompanyOverview, refreshOverview])

  return (
    <section className="space-y-6 text-slate-800">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-sky-700">{isWorker ? 'Worker workspace' : user?.role_name === 'SUPER_ADMIN' ? 'Platform workspace' : user?.company_id ? 'Company workspace' : 'Secure workspace'}</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{canViewCompanyOverview ? 'Company overview' : `Welcome, ${user?.full_name || user?.username || 'Administrator'}`}</h1>
          <p className="mt-2 text-slate-500">{isWorker ? 'Your personal work and performance overview.' : canViewCompanyOverview ? 'A live snapshot of inventory and your factory team.' : user?.company_id ? 'Your account is connected to your company workspace.' : 'Your GBMS business workspace.'}</p>
        </div>
        {canViewCompanyOverview && <button type="button" onClick={refreshOverview} disabled={overviewLoading} className="inline-flex items-center justify-center gap-2 self-start rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60 sm:self-auto"><RefreshCw size={15} className={overviewLoading ? 'animate-spin' : ''} />Refresh</button>}
      </header>

      {isLoading && <p className="text-sm text-slate-500" role="status">Loading your workspace…</p>}
      {error && <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{error}</p>}
      {overviewError && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Could not load the company overview: {overviewError}. If this mentions a missing column, run the updated GBMS_DB.sql script in SSMS.</p>}

      {canViewCompanyOverview && overview && <>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-medium text-slate-500">Revenue</p><p className="mt-3 text-3xl font-semibold tracking-tight text-slate-800">—</p>
            <p className="mt-2 text-sm text-slate-500">Sales records are not tracked yet.</p>
          </article>
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-medium text-slate-500">Active products</p><p className="mt-3 text-3xl font-semibold tracking-tight text-slate-800">{overview.inventory.active_product_count}</p>
            <p className="mt-2 text-sm text-slate-500">Products with on-hand stock levels</p>
          </article>
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-medium text-slate-500">Worker accounts</p><p className="mt-3 text-3xl font-semibold tracking-tight text-slate-800">{overview.workers.total}</p>
            <p className="mt-2 text-sm text-slate-500">{overview.workers.active_accounts} active account{overview.workers.active_accounts === 1 ? '' : 's'} enabled</p>
          </article>
        </div>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(280px,0.8fr)]">
          <InventoryChart items={overview.inventory.items} />
          <WorkersChart workers={overview.workers} />
        </div>
        <p className="text-right text-xs text-slate-400">Auto-refreshes every 15 seconds{overview.generated_at ? ` · Last updated ${new Date(overview.generated_at).toLocaleTimeString()}` : ''}</p>
      </>}

      {!canViewCompanyOverview && dashboard && !isWorker && <div className="grid gap-5 sm:grid-cols-2">
        <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><ShieldCheck className="text-sky-600" aria-hidden="true" /><h2 className="mt-4 font-semibold">Account access</h2><p className="mt-1 text-sm text-slate-500">{dashboard.message}</p></article>
        <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><p className="text-sm text-slate-500">Signed in as</p><p className="mt-2 text-lg font-semibold">{user?.username}</p><p className="mt-1 text-sm text-slate-500">Role: {user?.role_name?.replaceAll('_', ' ') || '—'}</p>{user?.company_id && <p className="mt-1 text-sm text-slate-500">Company workspace #{user.company_id}</p>}</article>
      </div>}

      {!canViewCompanyOverview && isWorker && dashboard && <WorkerPerformance />}

      {!canViewCompanyOverview && !isWorker && !isLoading && !error && <section aria-labelledby="available-modules-title">
        <div className="mb-4"><h2 id="available-modules-title" className="text-lg font-semibold">Your available workspace</h2><p className="mt-1 text-sm text-slate-500">Modules appear here based on your account permissions.</p></div>
        {modules.length ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{modules.map(({ title, text, path, icon: Icon }) => <Link key={path} to={path} className="group flex items-start gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-sky-200 hover:shadow-md"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-sky-50 text-sky-700"><Icon size={20} /></span><span><strong className="block font-semibold text-slate-800">{title}</strong><span className="mt-1 block text-sm text-slate-500">{text}</span><span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-sky-700">Open module <ArrowRight size={13} className="transition group-hover:translate-x-0.5" /></span></span></Link>)}</div> : <p className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600">Your account can view this dashboard. Ask your company administrator if you need access to another module.</p>}
      </section>}
    </section>
  )
}
