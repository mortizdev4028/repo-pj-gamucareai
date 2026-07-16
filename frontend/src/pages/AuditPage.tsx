import { useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogContent,
  DialogTitle, Grid, MenuItem, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, TextField, Typography,
} from '@mui/material'
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded'
import FactCheckRoundedIcon from '@mui/icons-material/FactCheckRounded'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { AuditLogEntry, AuditStats } from '../types'

const outcomeColor: Record<string, 'success' | 'error' | 'warning' | 'default'> = {
  success: 'success', failed: 'error', blocked: 'warning',
}

function pretty(value?: Record<string, unknown>) {
  return value ? JSON.stringify(value, null, 2) : 'Sin datos'
}

export function AuditPage() {
  const { user } = useAuth()
  const [entries, setEntries] = useState<AuditLogEntry[]>([])
  const [stats, setStats] = useState<AuditStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<AuditLogEntry | null>(null)
  const [actor, setActor] = useState('')
  const [action, setAction] = useState('')
  const [entityType, setEntityType] = useState('')
  const [outcome, setOutcome] = useState('')

  const params = useMemo(() => ({
    actor: actor || undefined,
    action: action || undefined,
    entity_type: entityType || undefined,
    outcome: outcome || undefined,
    limit: 250,
  }), [actor, action, entityType, outcome])

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [eventsResponse, statsResponse] = await Promise.all([
        api.get<AuditLogEntry[]>('/audit', { params }),
        api.get<AuditStats>('/audit/stats'),
      ])
      setEntries(eventsResponse.data)
      setStats(statsResponse.data)
    } catch {
      setError('No se ha podido cargar el registro de auditoria.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [params])

  const exportCsv = async () => {
    const response = await api.get('/audit/export.csv', { params, responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = 'gamucare_audit.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Stack spacing={3}>
      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" spacing={2}>
        <Box>
          <Typography variant="h4">Auditoria y actividad</Typography>
          <Typography color="text.secondary">Trazabilidad de accesos y cambios relevantes, con datos sensibles ocultos.</Typography>
        </Box>
        {user?.role === 'technical' && (
          <Button variant="outlined" startIcon={<DownloadRoundedIcon />} onClick={() => void exportCsv()}>
            Exportar CSV
          </Button>
        )}
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}

      <Grid container spacing={2}>
        {[
          ['Eventos totales', stats?.total_events ?? 0],
          ['Ultimas 24 horas', stats?.events_last_24h ?? 0],
          ['Actores', stats?.unique_actors ?? 0],
          ['Fallidos o bloqueados', stats?.failed_events ?? 0],
        ].map(([label, value]) => (
          <Grid item xs={12} sm={6} lg={3} key={String(label)}>
            <Card><CardContent><Typography color="text.secondary">{label}</Typography><Typography variant="h4">{value}</Typography></CardContent></Card>
          </Grid>
        ))}
      </Grid>

      <Card>
        <CardContent>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <TextField fullWidth label="Usuario" value={actor} onChange={(event) => setActor(event.target.value)} />
            <TextField fullWidth label="Accion exacta" value={action} onChange={(event) => setAction(event.target.value)} />
            <TextField fullWidth label="Entidad" value={entityType} onChange={(event) => setEntityType(event.target.value)} />
            <TextField select fullWidth label="Resultado" value={outcome} onChange={(event) => setOutcome(event.target.value)}>
              <MenuItem value="">Todos</MenuItem>
              <MenuItem value="success">Correcto</MenuItem>
              <MenuItem value="failed">Fallido</MenuItem>
              <MenuItem value="blocked">Bloqueado</MenuItem>
            </TextField>
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent sx={{ p: 0 }}>
          {loading ? <Box sx={{ p: 4, textAlign: 'center' }}><CircularProgress /></Box> : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Fecha</TableCell><TableCell>Usuario</TableCell><TableCell>Accion</TableCell>
                    <TableCell>Entidad</TableCell><TableCell>Resultado</TableCell><TableCell>Solicitud</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {entries.map((entry) => (
                    <TableRow key={entry.id} hover onClick={() => setSelected(entry)} sx={{ cursor: 'pointer' }}>
                      <TableCell>{new Date(entry.created_at).toLocaleString('es-ES')}</TableCell>
                      <TableCell>{entry.actor_email || 'Anonimo'}</TableCell>
                      <TableCell>{entry.action}</TableCell>
                      <TableCell>{entry.entity_type}{entry.entity_id ? ` · ${entry.entity_id.slice(0, 8)}` : ''}</TableCell>
                      <TableCell><Chip size="small" color={outcomeColor[entry.outcome] || 'default'} label={entry.outcome} /></TableCell>
                      <TableCell>{entry.request_id?.slice(0, 12) || '—'}</TableCell>
                    </TableRow>
                  ))}
                  {!entries.length && <TableRow><TableCell colSpan={6}>No hay eventos para los filtros seleccionados.</TableCell></TableRow>}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      <Dialog open={Boolean(selected)} onClose={() => setSelected(null)} fullWidth maxWidth="md">
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><FactCheckRoundedIcon /> Detalle de auditoria</DialogTitle>
        <DialogContent>
          {selected && <Stack spacing={2}>
            <Typography><strong>Accion:</strong> {selected.action}</Typography>
            <Typography><strong>Usuario:</strong> {selected.actor_email || 'Anonimo'}</Typography>
            <Typography><strong>IP:</strong> {selected.ip_address || 'No disponible'}</Typography>
            <Typography><strong>User-Agent:</strong> {selected.user_agent || 'No disponible'}</Typography>
            <Box><Typography fontWeight={700}>Antes</Typography><Box component="pre" sx={{ whiteSpace: 'pre-wrap', bgcolor: '#f6f3fb', p: 2, borderRadius: 2 }}>{pretty(selected.before_values)}</Box></Box>
            <Box><Typography fontWeight={700}>Despues</Typography><Box component="pre" sx={{ whiteSpace: 'pre-wrap', bgcolor: '#f6f3fb', p: 2, borderRadius: 2 }}>{pretty(selected.after_values)}</Box></Box>
            <Box><Typography fontWeight={700}>Detalle</Typography><Box component="pre" sx={{ whiteSpace: 'pre-wrap', bgcolor: '#f6f3fb', p: 2, borderRadius: 2 }}>{pretty(selected.details)}</Box></Box>
          </Stack>}
        </DialogContent>
      </Dialog>
    </Stack>
  )
}
