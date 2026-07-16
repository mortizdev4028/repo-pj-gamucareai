import { useState } from 'react'
import { Alert, Box, Button, Card, CardContent, CircularProgress, Stack, TextField, Typography } from '@mui/material'
import LockResetRoundedIcon from '@mui/icons-material/LockResetRounded'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function ChangePasswordPage() {
  const { user, changePassword, logout } = useAuth()
  const navigate = useNavigate()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (!user) return <Navigate to="/login" replace />

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    if (newPassword !== confirmPassword) {
      setError('Las nuevas contrasenas no coinciden.')
      return
    }
    setLoading(true)
    try {
      await changePassword(currentPassword, newPassword)
      navigate('/security', { replace: true })
    } catch (caught: any) {
      const detail = caught?.response?.data?.detail
      setError(Array.isArray(detail) ? detail.join('. ') : detail || 'No se ha podido cambiar la contrasena.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', bgcolor: '#f8f7fc', p: 2 }}>
      <Card sx={{ width: '100%', maxWidth: 560 }}>
        <CardContent sx={{ p: { xs: 3, sm: 5 } }}>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 3 }}>
            <LockResetRoundedIcon color="primary" sx={{ fontSize: 48 }} />
            <Box>
              <Typography variant="h4">Cambiar contrasena</Typography>
              <Typography color="text.secondary">
                {user.must_change_password ? 'Debes sustituir la contrasena temporal antes de continuar.' : 'Actualiza tus credenciales de acceso.'}
              </Typography>
            </Box>
          </Stack>
          <Alert severity="info" sx={{ mb: 3 }}>
            Usa al menos 12 caracteres, mayuscula, minuscula, numero y caracter especial.
          </Alert>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <Box component="form" onSubmit={submit}>
            <TextField fullWidth type="password" label="Contrasena actual" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} sx={{ mb: 2 }} />
            <TextField fullWidth type="password" label="Nueva contrasena" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} sx={{ mb: 2 }} />
            <TextField fullWidth type="password" label="Repite la nueva contrasena" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} sx={{ mb: 3 }} />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <Button fullWidth type="submit" variant="contained" disabled={loading}>
                {loading ? <CircularProgress size={24} color="inherit" /> : 'Guardar contrasena'}
              </Button>
              <Button fullWidth variant="outlined" onClick={() => void logout()}>Cerrar sesion</Button>
            </Stack>
          </Box>
        </CardContent>
      </Card>
    </Box>
  )
}
