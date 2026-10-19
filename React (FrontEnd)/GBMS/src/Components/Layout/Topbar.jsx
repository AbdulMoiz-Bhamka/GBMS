// src/Components/Layout/Topbar.jsx
import { useEffect, useRef, useState } from 'react'
import { Bell, ChevronDown, KeyRound, LogOut, Menu, Search, UserRound } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'

export default function Topbar({ onMenuClick = () => {} }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const profileRef = useRef(null)
  const [search, setSearch] = useState('')
  const [profileOpen, setProfileOpen] = useState(false)

  useEffect(() => {
    if (!profileOpen) return undefined
    const closeOnOutsideClick = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) setProfileOpen(false)
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setProfileOpen(false)
    }
    document.addEventListener('pointerdown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [profileOpen])

  const handleLogout = () => {
    setProfileOpen(false)
    logout()
    navigate('/', { replace: true })
  }
  const displayName = user?.full_name || user?.username || 'Administrator'
  const initials = displayName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase()

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="flex min-h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <button type="button" aria-label="Open navigation menu" onClick={onMenuClick} className="rounded-lg p-2 text-slate-600 transition hover:bg-slate-100 lg:hidden">
            <Menu size={20} />
          </button>
          <div className="hidden min-w-0 sm:block">
            <p className="truncate text-sm font-semibold text-slate-800">Business Workspace</p>
            <p className="text-xs text-slate-500">Manage your garment business</p>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-4">
          <form role="search" className="hidden md:block" onSubmit={(event) => event.preventDefault()}>
            <label className="relative block">
              <span className="sr-only">Search</span>
              <Search size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search..." className="w-44 rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none transition focus:border-sky-500 focus:bg-white focus:ring-2 focus:ring-sky-100 lg:w-60" />
            </label>
          </form>

          <button type="button" aria-label="Notifications" title="Notifications" className="relative rounded-xl p-2.5 text-slate-600 transition hover:bg-slate-100">
            <Bell size={19} />
          </button>

          <div ref={profileRef} className="relative">
            <button type="button" aria-label="Open account menu" aria-expanded={profileOpen} aria-haspopup="menu" onClick={() => setProfileOpen((open) => !open)} className="flex items-center gap-2 rounded-xl p-1.5 transition hover:bg-slate-100">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-100 text-sm font-semibold text-sky-800">
                {initials || <UserRound size={18} />}
              </span>
              <span className="hidden text-left sm:block">
                <span className="block max-w-36 truncate text-sm font-semibold text-slate-800">{displayName}</span>
                <span className="block text-xs text-slate-500">{user?.role_name || 'Administrator'}</span>
              </span>
              <ChevronDown size={16} className="hidden text-slate-400 sm:block" />
            </button>

            {profileOpen && (
              <div role="menu" className="absolute right-0 top-full mt-2 w-52 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
                <div className="border-b border-slate-100 px-3 py-2">
                  <p className="truncate text-sm font-semibold text-slate-800">{displayName}</p>
                  <p className="text-xs text-slate-500">{user?.role_name || 'Administrator'}</p>
                </div>
                <button type="button" role="menuitem" onClick={() => { setProfileOpen(false); navigate('/security') }} className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
                  <KeyRound size={16} /> Password &amp; security
                </button>
                <button type="button" role="menuitem" onClick={handleLogout} className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50">
                  <LogOut size={16} /> Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
