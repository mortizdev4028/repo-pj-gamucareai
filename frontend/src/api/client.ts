import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

const baseURL = import.meta.env.VITE_API_URL || '/api/v1'
const TOKEN_KEY = 'gamucare_access_token'

// Migrate tokens from versions prior to v0.10.0. The access token is now kept
// in sessionStorage, while the refresh token lives in an HttpOnly cookie.
const legacyToken = localStorage.getItem('gamucare_token')
if (legacyToken && !sessionStorage.getItem(TOKEN_KEY)) {
  sessionStorage.setItem(TOKEN_KEY, legacyToken)
}
localStorage.removeItem('gamucare_token')

export function getAccessToken() {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setAccessToken(token: string) {
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearAccessToken() {
  sessionStorage.removeItem(TOKEN_KEY)
}

export const api = axios.create({ baseURL, withCredentials: true })

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = axios.post<{ access_token: string }>(
      `${baseURL}/auth/refresh`,
      {},
      { withCredentials: true },
    ).then((response) => {
      setAccessToken(response.data.access_token)
      return response.data.access_token
    }).finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryConfig | undefined
    const path = original?.url || ''
    const canRefresh = error.response?.status === 401
      && original
      && !original._retry
      && !path.includes('/auth/login')
      && !path.includes('/auth/refresh')

    if (canRefresh) {
      original._retry = true
      try {
        const token = await refreshAccessToken()
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      } catch {
        // Fall through to the common logout behaviour.
      }
    }

    if (error.response?.status === 401) {
      clearAccessToken()
      if (!window.location.pathname.includes('/login')) window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)
