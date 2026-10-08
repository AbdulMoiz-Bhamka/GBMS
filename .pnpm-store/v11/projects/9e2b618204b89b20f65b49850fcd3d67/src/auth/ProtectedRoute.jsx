// src/auth/ProtectedRoute.jsx
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './useAuth'

export default function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  if (isLoading) return <main className="grid min-h-screen place-items-center bg-slate-50 text-slate-600">Loading workspace…</main>
  return user ? <Outlet /> : <Navigate to="/" replace />
}
