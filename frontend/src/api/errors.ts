import axios from 'axios'

interface ErrorPayload {
  detail?: string
  error_code?: string
  request_id?: string
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError<ErrorPayload>(error)) return fallback
  const detail = error.response?.data?.detail
  const requestId = error.response?.data?.request_id || error.response?.headers?.['x-request-id']
  const message = typeof detail === 'string' && detail.trim() ? detail : fallback
  return requestId ? `${message} (solicitud ${requestId})` : message
}
