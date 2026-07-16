import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { DashboardPage } from '../pages/DashboardPage'

/** Route the technical profile away from business dashboards. */
export function HomeRoute() {
  const { user } = useAuth()
  if (user?.role === 'technical') return <Navigate to="/system-status" replace />
  return <DashboardPage />
}
