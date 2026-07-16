import { useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Stack, TextField, Typography } from '@mui/material'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import logo from '../assets/logo.png'
import { APP_ENV, APP_VERSION, RELEASE_LABEL } from '../version'

const demoUsers = [
  ['Clinica · gestion', 'clinic@gamucare.local'],
  ['Personal · solo lectura', 'staff@gamucare.local'],
  ['Tecnico', 'technical@gamucare.local'],
  ['Propietario', 'owner01@example.test']
]

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('clinic@gamucare.local')
  const [password, setPassword] = useState('GamuCare123!')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (user) return <Navigate to={user.must_change_password ? '/change-password' : user.role === 'technical' ? '/system-status' : '/'} replace />

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const profile = await login(email, password)
      navigate(profile.must_change_password ? '/change-password' : profile.role === 'technical' ? '/system-status' : '/')
    } catch (caught) {
      setError('No se ha podido iniciar sesion. Revisa las credenciales y el estado de la API.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.15fr .85fr' }, bgcolor: '#f8f7fc' }}>
      <Box sx={{ display: { xs: 'none', md: 'flex' }, p: 7, color: 'white', position: 'relative', overflow: 'hidden', background: 'linear-gradient(145deg, #7c3aed 0%, #ec4899 55%, #f59e0b 100%)' }}>
        <Box sx={{ maxWidth: 640, alignSelf: 'center', zIndex: 1 }}>
          <img src={logo} alt="GamuCare AI" width={150} height={150} style={{ objectFit: 'contain', background: 'rgba(255,255,255,.92)', borderRadius: 36, padding: 12 }} />
          <Typography variant="h2" sx={{ mt: 3, fontSize: { md: 52, lg: 68 } }}>La salud de tu mascota, siempre al dia.</Typography>
          <Typography sx={{ mt: 2, fontSize: 20, opacity: .92 }}>Planes LifeCare, seguimiento preventivo y respuestas documentadas en una sola aplicacion.</Typography>
        </Box>
      </Box>
      <Box sx={{ display: 'grid', placeItems: 'center', p: 2 }}>
        <Card sx={{ width: '100%', maxWidth: 520 }}>
          <CardContent sx={{ p: { xs: 3, sm: 5 } }}>
            <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 3 }}>
              <img src={logo} alt="Logo" width={70} height={70} />
              <Box>
                <Typography variant="h4">GamuCare AI</Typography>
                <Typography color="text.secondary">Acceso al portal</Typography>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: .5 }}>
                  <Typography variant="caption" color="text.disabled">v{APP_VERSION}</Typography>
                  <Chip size="small" label={`${APP_ENV.toUpperCase()} · ${RELEASE_LABEL}`} color="warning" variant="outlined" />
                </Stack>
              </Box>
            </Stack>
            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            <Box component="form" onSubmit={submit}>
              <TextField fullWidth label="Correo electronico" value={email} onChange={(event) => setEmail(event.target.value)} sx={{ mb: 2 }} />
              <TextField fullWidth type="password" label="Contrasena" value={password} onChange={(event) => setPassword(event.target.value)} sx={{ mb: 2 }} />
              <Button fullWidth size="large" variant="contained" type="submit" disabled={loading}>
                {loading ? <CircularProgress size={24} color="inherit" /> : 'Entrar'}
              </Button>
            </Box>
            <Typography variant="subtitle2" sx={{ mt: 4, mb: 1 }}>Accesos de demostracion</Typography>
            <Stack direction="row" flexWrap="wrap" gap={1}>
              {demoUsers.map(([label, value]) => <Chip key={value} label={label} onClick={() => setEmail(value)} />)}
            </Stack>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 2 }}>Contrasena comun: GamuCare123!</Typography>
          </CardContent>
        </Card>
      </Box>
    </Box>
  )
}
