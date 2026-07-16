import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import type { Role } from '../types'

interface RoleRouteProps {
  allowed: Role[]
  children: React.ReactNode
}

export function RoleRoute({ allowed, children }: RoleRouteProps) {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace />
  if (!allowed.includes(user.role)) {
    return <Navigate to="/forbidden" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}
