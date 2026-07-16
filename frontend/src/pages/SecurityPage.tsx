import { useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Divider,
  IconButton, Stack, TextField, Tooltip, Typography,
} from '@mui/material'
import DevicesRoundedIcon from '@mui/icons-material/DevicesRounded'
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import PasswordRoundedIcon from '@mui/icons-material/PasswordRounded'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { SecuritySession } from '../types'

function dateTime(value?: string) {
  return value ? new Date(value).toLocaleString('es-ES') : '—'
}

export function SecurityPage() {
  const { user, changePassword } = useAuth()
  const [sessions, setSessions] = useState<SecuritySession[]>([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const loadSessions = async () => {
    setLoading(true)
    try {
      const response = await api.get<SecuritySession[]>('/auth/sessions')
      setSessions(response.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void loadSessions() }, [])

  const revoke = async (session: SecuritySession) => {
    await api.delete(`/auth/sessions/${session.id}`)
    await loadSessions()
  }

  const submitPassword = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setMessage('')
    if (newPassword !== confirmPassword) {
      setError('Las nuevas contrasenas no coinciden.')
      return
    }
    try {
      await changePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setMessage('Contrasena actualizada. Las sesiones anteriores han sido revocadas.')
      await loadSessions()
    } catch (caught: any) {
      const detail = caught?.response?.data?.detail
      setError(Array.isArray(detail) ? detail.join('. ') : detail || 'No se ha podido cambiar la contrasena.')
    }
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Seguridad de la cuenta</Typography>
        <Typography color="text.secondary">Gestiona tu contrasena y revisa las sesiones abiertas.</Typography>
      </Box>

      {message && <Alert severity="success">{message}</Alert>}
      {error && <Alert severity="error">{error}</Alert>}

      <Card>
        <CardContent>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
            <PasswordRoundedIcon color="primary" />
            <Box>
              <Typography variant="h6">Cambiar contrasena</Typography>
              <Typography variant="body2" color="text.secondary">Usuario: {user?.email}</Typography>
            </Box>
          </Stack>
          <Box component="form" onSubmit={submitPassword}>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
              <TextField fullWidth type="password" label="Contrasena actual" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
              <TextField fullWidth type="password" label="Nueva contrasena" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
              <TextField fullWidth type="password" label="Confirmacion" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
            </Stack>
            <Button type="submit" variant="contained" sx={{ mt: 2 }}>Actualizar contrasena</Button>
          </Box>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
            <DevicesRoundedIcon color="primary" />
            <Box>
              <Typography variant="h6">Sesiones recientes</Typography>
              <Typography variant="body2" color="text.secondary">Los tokens de renovacion se rotan y pueden revocarse individualmente.</Typography>
            </Box>
          </Stack>
          {loading ? <CircularProgress /> : (
            <Stack divider={<Divider flexItem />}>
              {sessions.map((session) => (
                <Stack key={session.id} direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }} sx={{ py: 2 }}>
                  <Box sx={{ flex: 1 }}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Typography fontWeight={700}>{session.ip_address || 'Direccion no disponible'}</Typography>
                      {session.current && <Chip size="small" color="success" label="Sesion actual" />}
                      {session.revoked_at && <Chip size="small" label="Revocada" />}
                    </Stack>
                    <Typography variant="body2" color="text.secondary" sx={{ wordBreak: 'break-word' }}>{session.user_agent || 'Navegador no identificado'}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Creada: {dateTime(session.created_at)} · Caduca: {dateTime(session.expires_at)}
                    </Typography>
                  </Box>
                  {!session.revoked_at && !session.current && (
                    <Tooltip title="Revocar sesion">
                      <IconButton color="error" onClick={() => void revoke(session)}><DeleteOutlineRoundedIcon /></IconButton>
                    </Tooltip>
                  )}
                </Stack>
              ))}
              {!sessions.length && <Typography color="text.secondary">No hay sesiones registradas.</Typography>}
            </Stack>
          )}
        </CardContent>
      </Card>
    </Stack>
  )
}
