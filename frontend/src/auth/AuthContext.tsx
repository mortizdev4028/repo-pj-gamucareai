import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api, clearAccessToken, getAccessToken, setAccessToken } from '../api/client'
import type { User } from '../types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>
  refreshProfile: () => Promise<User>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshProfile = async () => {
    const profile = await api.get<User>('/auth/me')
    setUser(profile.data)
    return profile.data
  }

  useEffect(() => {
    const restore = async () => {
      try {
        if (!getAccessToken()) {
          const refreshed = await api.post<{ access_token: string }>('/auth/refresh')
          setAccessToken(refreshed.data.access_token)
        }
        await refreshProfile()
      } catch {
        clearAccessToken()
      } finally {
        setLoading(false)
      }
    }
    void restore()
  }, [])

  const login = async (email: string, password: string) => {
    const response = await api.post<{ access_token: string }>('/auth/login', { email, password })
    setAccessToken(response.data.access_token)
    return refreshProfile()
  }

  const logout = async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      // The local session must still be cleared when the server is unavailable.
    }
    clearAccessToken()
    setUser(null)
  }

  const changePassword = async (currentPassword: string, newPassword: string) => {
    const response = await api.post<{ access_token: string }>('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    setAccessToken(response.data.access_token)
    await refreshProfile()
  }

  const value = useMemo(
    () => ({ user, loading, login, logout, changePassword, refreshProfile }),
    [user, loading],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return context
}
