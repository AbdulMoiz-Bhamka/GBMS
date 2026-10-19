// src/Components/Layout/Sidebar.jsx
import { NavLink } from 'react-router-dom'
import {
  ArrowUpRight, BarChart3, Building2, ClipboardList, Layers3,
  Settings, ShoppingCart, Users, Wallet, Warehouse, X,
} from 'lucide-react'
import { useAuth } from '../../auth/useAuth'

export default function Sidebar({ isOpen = false, onClose = () => {} }) {
  const { user } = useAuth()
  const isSuperAdmin = user?.role_name === 'SUPER_ADMIN'
  const isWorker = user?.role_name === 'WORKER'
  const hasPermission = (code) => user?.company_id != null && user?.permissions?.includes(code)
  const navigationGroups = [
    { title: 'OVERVIEW', items: [{ label: 'Overview', path: '/dashboard', icon: BarChart3, available: true }] },
    ...(isSuperAdmin ? [{ title: 'PLATFORM', items: [{ label: 'Companies', path: '/companies', icon: Building2, available: true }] }] : []),
    ...((hasPermission('users.view') || hasPermission('inventory.view')) ? [{ title: 'COMPANY', items: [
      ...(hasPermission('users.view') ? [{ label: 'Team and access', path: '/users', icon: Users, available: true }] : []),
      ...(hasPermission('inventory.view') ? [{ label: 'Inventory', path: '/inventory', icon: Warehouse, available: true }] : []),
    ] }] : []),
    ...(!isWorker ? [{
      title: 'COMING SOON',
      items: [
        { label: 'Production', icon: Layers3 },
        { label: 'Purchasing', icon: ShoppingCart },
        { label: 'Sales', icon: ArrowUpRight },
        { label: 'Employees', icon: Users },
        { label: 'Finance', icon: Wallet },
        { label: 'Assets', icon: Building2 },
        { label: 'Reports', icon: ClipboardList },
      ],
    }] : []),
  ]

  return (
    <>
      {isOpen && <button type="button" aria-label="Close navigation menu" className="fixed inset-0 z-40 bg-slate-900/30 lg:hidden" onClick={onClose} />}
      <aside className={`fixed inset-y-0 left-0 z-50 flex min-h-screen w-64 shrink-0 flex-col overflow-y-auto border-r border-[#e8edf0] bg-white px-4 py-5 transition-transform duration-200 lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:translate-x-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="mb-8 flex items-center gap-3 px-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#345c74] text-lg font-bold text-white">G</span>
          <div><h2 className="text-sm font-extrabold tracking-wide text-[#345c74]">GBMS</h2><p className="text-xs text-[#7d8c98]">Business Management</p></div>
          <button type="button" aria-label="Close navigation menu" onClick={onClose} className="ml-auto rounded-lg p-2 text-[#526574] hover:bg-[#f7f9fa] lg:hidden"><X size={18} /></button>
        </div>

        <nav className="flex-1 space-y-6">
          {navigationGroups.map((group) => (
            <section key={group.title}>
              <h3 className="mb-2 px-3 text-[10px] font-bold tracking-[0.12em] text-[#7d8c98]">{group.title}</h3>
              <div className="space-y-1">
                {group.items.map((item) => {
                  const Icon = item.icon
                  return item.available ? (
                    <NavLink key={item.path} to={item.path} onClick={onClose} className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${isActive ? 'bg-[#edf3f6] font-semibold text-[#345c74]' : 'text-[#526574] hover:bg-[#f7f9fa] hover:text-[#345c74]'}`}>
                      <Icon size={17} strokeWidth={1.8} /><span>{item.label}</span>
                    </NavLink>
                  ) : (
                    <div key={item.label} title="This module is not available yet" aria-disabled="true" className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400">
                      <Icon size={17} strokeWidth={1.8} /><span>{item.label}</span><span className="ml-auto text-[9px] uppercase tracking-wide">Soon</span>
                    </div>
                  )
                })}
              </div>
            </section>
          ))}
        </nav>

        <div className="mt-6 border-t border-[#e8edf0] pt-4">
          <button type="button" disabled title="Settings are not available yet" className="flex w-full cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400"><Settings size={17} strokeWidth={1.8} />Settings <span className="ml-auto text-[9px] uppercase tracking-wide">Soon</span></button>
        </div>
      </aside>
    </>
  )
}
