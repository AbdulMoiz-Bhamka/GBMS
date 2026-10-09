// src/Components/Layout/Sidebar.jsx

import { NavLink } from 'react-router-dom'
import { BarChart3, Warehouse, Layers3, ShoppingCart, ArrowUpRight, Users, Wallet, Building2, ClipboardList, Settings, X } from 'lucide-react'

const Sidebar = ({ isOpen = false, onClose = () => {} }) => {

    const navigationGroups = [
        {
            title: 'OVERVIEW',
            items: [
                { label: 'Overview', path: '/dashboard', icon: BarChart3 },
            ],
        },
        {
            title: 'BUSINESS',
            items: [
                { label: 'Inventory', path: '/inventory', icon: Warehouse },
                { label: 'Production', path: '/production', icon: Layers3 },
                { label: 'Purchasing', path: '/purchasing', icon: ShoppingCart },
                { label: 'Sales', path: '/sales', icon: ArrowUpRight },
            ],
        },
        {
            title: 'MANAGEMENT',
            items: [
                { label: 'Employees', path: '/employees', icon: Users },
                { label: 'Finance', path: '/finance', icon: Wallet },
                { label: 'Assets', path: '/assets', icon: Building2 }
            ],
        },
        {
            title: 'ANALYTICS',
            items: [
                { label: 'Reports', path: '/report', icon: ClipboardList }
            ]
        }
    ]

    return (
        <>
            {isOpen && <button type="button" aria-label="Close navigation menu" className="fixed inset-0 z-40 bg-slate-900/30 lg:hidden" onClick={onClose} />}
            <aside className={`fixed inset-y-0 left-0 z-50 flex min-h-screen w-64 shrink-0 flex-col border-r border-[#e8edf0] bg-white px-4 py-5 transition-transform duration-200 lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:translate-x-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
            <div className="mb-8 flex items-center gap-3 px-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#345c74] text-lg font-bold text-white">
                    G
                </span>

                <div>
                    <h2 className="text-sm font-extrabold tracking-wide text-[#345c74]">
                        GBMS
                    </h2>
                    <p className="text-xs text-[#7d8c98]">
                        Business Management
                    </p>
                </div>
                <button type="button" aria-label="Close navigation menu" onClick={onClose} className="ml-auto rounded-lg p-2 text-[#526574] hover:bg-[#f7f9fa] lg:hidden"><X size={18} /></button>
            </div>

            <nav className="flex-1 space-y-7">
                {navigationGroups.map((group) => (
                    <section key={group.title}>
                        <h3 className="mb-2 px-3 text-[10px] font-bold tracking-[0.12em] text-[#7d8c98]">
                            {group.title}
                        </h3>

                        <div className="space-y-1">
                            {group.items.map((item) => {
                                const Icon = item.icon

                                return (
                                    <NavLink
                                        key={item.path}
                                        to={item.path}
                                        onClick={onClose}
                                        className={({ isActive }) =>
                                            `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${isActive
                                                ? 'bg-[#edf3f6] font-semibold text-[#345c74]'
                                                : 'text-[#526574] hover:bg-[#f7f9fa] hover:text-[#345c74]'
                                            }`
                                        }
                                    >
                                        <Icon size={17} strokeWidth={1.8} />
                                        <span>{item.label}</span>
                                    </NavLink>
                                )
                            })}
                        </div>
                    </section>
                ))}
            </nav>

            <div className="border-t border-[#e8edf0] pt-4">
                <button
                    type="button"
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-[#526574] hover:bg-[#f7f9fa]"
                >
                    <Settings size={17} strokeWidth={1.8} />
                    Settings
                </button>
            </div>
            </aside>
        </>
    )
}

export default Sidebar
