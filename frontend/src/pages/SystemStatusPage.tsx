import { useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Link,
  Stack, Typography
} from '@mui/material'
import MonitorHeartRoundedIcon from '@mui/icons-material/MonitorHeartRounded'
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded'
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded'
import { api } from '../api/client'
import type { ObservabilityStatus } from '../types'

const labels: Record<string, string> = {
  postgres: 'PostgreSQL',
  qdrant: 'Qdrant',
  ollama: 'Ollama'
}

export function SystemStatusPage() {
  const [data, setData] = useState<ObservabilityStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get<ObservabilityStatus>('/observability/status')
      setData(response.data)
    } catch {
      setError('No se pudo consultar el estado tecnico del sistema.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Estado tecnico</Typography>
        <Typography color="text.secondary">Disponibilidad y latencia de los servicios que utiliza GamuCare AI.</Typography>
      </Box>
      {error && <Alert severity="error">{error}</Alert>}
      <Stack direction={{ xs: 'column', md: 'row' }} gap={2} alignItems={{ md: 'center' }} justifyContent="space-between">
        <Stack direction="row" gap={1} alignItems="center">
          <MonitorHeartRoundedIcon color={data?.status === 'ok' ? 'success' : 'warning'} />
          <Chip color={data?.status === 'ok' ? 'success' : 'warning'} label={data?.status === 'ok' ? 'Servicios disponibles' : 'Funcionamiento degradado'} />
          {data && <Typography variant="body2" color="text.secondary">v{data.version} · {new Date(data.checked_at).toLocaleString()}</Typography>}
        </Stack>
        <Button variant="outlined" startIcon={<RefreshRoundedIcon />} onClick={() => void load()}>Actualizar</Button>
      </Stack>

      {loading ? <CircularProgress /> : (
        <Stack direction={{ xs: 'column', md: 'row' }} gap={2}>
          {Object.entries(data?.dependencies || {}).map(([name, item]) => (
            <Card key={name} sx={{ flex: 1 }}>
              <CardContent>
                <Typography variant="caption" color="text.secondary">{labels[name] || name}</Typography>
                <Typography variant="h5" fontWeight={850} mt={0.5}>{item.status === 'up' ? 'Disponible' : 'No disponible'}</Typography>
                <Chip sx={{ mt: 1 }} size="small" color={item.status === 'up' ? 'success' : 'error'} label={`${item.latency_ms.toFixed(1)} ms`} />
                {item.error && <Typography variant="body2" color="error" mt={1}>{item.error}</Typography>}
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}

      <Card><CardContent>
        <Typography variant="h6">Monitorizacion avanzada</Typography>
        <Typography variant="body2" color="text.secondary" mb={2}>
          Los paneles se levantan con el perfil monitoring. Grafana muestra disponibilidad, errores, latencias, VetIA, Qdrant, Ollama y PostgreSQL.
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} gap={1}>
          <Button component={Link} href={data?.monitoring.grafana_url || 'http://localhost:3000'} target="_blank" variant="contained" endIcon={<OpenInNewRoundedIcon />}>Grafana</Button>
          <Button component={Link} href={data?.monitoring.prometheus_url || 'http://localhost:9090'} target="_blank" variant="outlined" endIcon={<OpenInNewRoundedIcon />}>Prometheus</Button>
          <Button component={Link} href={data?.monitoring.alertmanager_url || 'http://localhost:9093'} target="_blank" variant="outlined" endIcon={<OpenInNewRoundedIcon />}>Alertas tecnicas</Button>
        </Stack>
      </CardContent></Card>

      <Alert severity="info">
        Inicia la monitorizacion con <code>.\scripts\start-monitoring.ps1</code>. Los backups se crean con <code>.\scripts\backup.ps1</code>.
      </Alert>
    </Stack>
  )
}
