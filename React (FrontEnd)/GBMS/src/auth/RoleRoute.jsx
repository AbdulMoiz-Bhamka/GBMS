import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './useAuth'

export default function RoleRoute({ allowedRoles }) {
  const { user, isLoading } = useAuth()
  if (isLoading) return <main className="grid min-h-screen place-items-center bg-slate-50 text-slate-600">Loading workspace…</main>
  if (!user) return <Navigate to="/" replace />
  return allowedRoles.includes(user.role_name)
    ? <Outlet />
    : <Navigate to="/dashboard" replace />
}
