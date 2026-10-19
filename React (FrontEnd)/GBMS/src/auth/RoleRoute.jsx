// src/auth/RoleRoute.jsx
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './useAuth'

export default function RoleRoute({ allowedRoles, requiredPermission, requiresCompany = false }) {
  const { user, isLoading } = useAuth()
  if (isLoading) return <main className="grid min-h-screen place-items-center bg-slate-50 text-slate-600">Loading workspace…</main>
  if (!user) return <Navigate to="/" replace />
  const allowedByRole = !allowedRoles || allowedRoles.includes(user.role_name)
  const allowedByPermission = !requiredPermission || user.permissions?.includes(requiredPermission)
  const allowedByCompany = !requiresCompany || user.company_id != null
  return allowedByRole && allowedByPermission && allowedByCompany
    ? <Outlet />
    : <Navigate to="/dashboard" replace />
}
