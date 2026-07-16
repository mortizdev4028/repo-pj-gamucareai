import React from 'react'
import { Alert, Box, Button, Paper, Typography } from '@mui/material'

interface State {
  failed: boolean
}

export class AppErrorBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Do not render stack traces to the user. Browser diagnostics remain available
    // to the technical profile during local troubleshooting.
    console.error('render_error', error, info)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', p: 2 }}>
        <Paper sx={{ width: 'min(560px, 100%)', p: { xs: 3, sm: 5 }, borderRadius: 4 }}>
          <Typography variant="h4" fontWeight={850} gutterBottom>La pantalla no ha podido cargarse</Typography>
          <Alert severity="error" sx={{ my: 2 }}>
            Se ha producido un error de interfaz. No se han mostrado detalles tecnicos ni datos sensibles.
          </Alert>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            Recarga la aplicacion. Si el problema continua, revisa los registros desde el perfil tecnico.
          </Typography>
          <Button variant="contained" onClick={() => window.location.reload()}>Recargar aplicacion</Button>
        </Paper>
      </Box>
    )
  }
}
