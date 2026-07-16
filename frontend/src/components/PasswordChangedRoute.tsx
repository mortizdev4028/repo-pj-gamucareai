import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function PasswordChangedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  if (user?.must_change_password) return <Navigate to="/change-password" replace />
  return <>{children}</>
}
