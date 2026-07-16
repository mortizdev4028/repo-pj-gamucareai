import { Alert, Box, Button, Paper, Typography } from '@mui/material'
import LockRoundedIcon from '@mui/icons-material/LockRounded'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function AccessDeniedPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const requested = (location.state as { from?: string } | null)?.from

  return (
    <Paper sx={{ maxWidth: 720, mx: 'auto', p: { xs: 3, sm: 5 }, borderRadius: 4 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <LockRoundedIcon color="warning" fontSize="large" />
        <Typography variant="h4" fontWeight={850}>Acceso no permitido</Typography>
      </Box>
      <Alert severity="warning" sx={{ mb: 2 }}>
        El perfil {user?.role || 'actual'} no tiene permisos para abrir esta seccion.
      </Alert>
      {requested && (
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          Ruta solicitada: <strong>{requested}</strong>
        </Typography>
      )}
      <Button variant="contained" onClick={() => navigate('/', { replace: true })}>Volver al inicio</Button>
    </Paper>
  )
}
