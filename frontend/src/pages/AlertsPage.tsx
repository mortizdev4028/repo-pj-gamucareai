import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog,
  DialogActions, DialogContent, DialogTitle, Divider, FormControl, InputLabel,
  Link, MenuItem, Select, Stack, TextField, Typography
} from '@mui/material'
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded'
import FactCheckRoundedIcon from '@mui/icons-material/FactCheckRounded'
import DoneAllRoundedIcon from '@mui/icons-material/DoneAllRounded'
import CancelRoundedIcon from '@mui/icons-material/CancelRounded'
import ReplayRoundedIcon from '@mui/icons-material/ReplayRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { AlertRebuildResult, AlertStats, PreventiveAlert, RiskRuleDefinition } from '../types'

type AlertStatus = 'new' | 'reviewed' | 'resolved' | 'dismissed'

const statusLabels: Record<AlertStatus, string> = {
  new: 'Nueva',
  reviewed: 'Revisada',
  resolved: 'Resuelta',
  dismissed: 'Descartada'
}

const severityLabels: Record<string, string> = {
  info: 'Informativa', low: 'Baja', medium: 'Media', high: 'Alta'
}

function errorMessage(error: unknown): string {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response
    if (response?.data?.detail) return response.data.detail
  }
  return 'No se pudo completar la operación.'
}

function evidenceLines(evidence: Record<string, unknown>): string[] {
  const hidden = new Set(['rag_sources', 'rag_enriched_at'])
  return Object.entries(evidence)
    .filter(([key]) => !hidden.has(key))
    .map(([key, value]) => {
      const formatted = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
      return `${key}: ${formatted}`
    })
}

export function AlertsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState<PreventiveAlert[]>([])
  const [rules, setRules] = useState<RiskRuleDefinition[]>([])
  const [stats, setStats] = useState<AlertStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState('active')
  const [severityFilter, setSeverityFilter] = useState('')
  const [speciesFilter, setSpeciesFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<PreventiveAlert | null>(null)
  const [action, setAction] = useState<AlertStatus>('reviewed')
  const [notes, setNotes] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params: Record<string, string | boolean> = {}
      if (statusFilter === 'active') params.active_only = true
      else if (statusFilter) params.status = statusFilter
      if (severityFilter) params.severity = severityFilter
      if (speciesFilter) params.species = speciesFilter
      if (categoryFilter) params.category = categoryFilter
      if (search.trim()) params.pet_name = search.trim()
      const [alertResponse, statsResponse, ruleResponse] = await Promise.all([
        api.get<PreventiveAlert[]>('/alerts', { params }),
        api.get<AlertStats>('/alerts/stats'),
        api.get<RiskRuleDefinition[]>('/alerts/rules')
      ])
      setAlerts(alertResponse.data)
      setStats(statsResponse.data)
      setRules(ruleResponse.data)
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setLoading(false)
    }
  }, [categoryFilter, search, severityFilter, speciesFilter, statusFilter])

  useEffect(() => { void load() }, [load])

  const categories = useMemo(
    () => Array.from(new Set(rules.map((rule) => rule.category))).sort(),
    [rules]
  )

  const rebuild = async (enrich: boolean) => {
    setWorking(true)
    setError('')
    setMessage('')
    try {
      const response = await api.post<AlertRebuildResult>('/alerts/rebuild', null, { params: { enrich } })
      const result = response.data
      setMessage(
        `Evaluación terminada: ${result.created} nuevas, ${result.updated} actualizadas, ` +
        `${result.resolved} resueltas y ${result.enriched} enriquecidas con VetIA.`
      )
      await load()
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setWorking(false)
    }
  }

  const openAction = (alert: PreventiveAlert, nextStatus: AlertStatus) => {
    setSelected(alert)
    setAction(nextStatus)
    setNotes(nextStatus === 'reviewed' ? (alert.review_notes || '') : '')
  }

  const submitAction = async () => {
    if (!selected) return
    setWorking(true)
    setError('')
    try {
      await api.patch(`/alerts/${selected.id}/status`, { status: action, notes: notes.trim() || null })
      setSelected(null)
      setNotes('')
      await load()
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setWorking(false)
    }
  }

  return (
    <Stack spacing={3}>
      <Box sx={{ display: 'flex', gap: 2, justifyContent: 'space-between', alignItems: { xs: 'flex-start', md: 'center' }, flexDirection: { xs: 'column', md: 'row' } }}>
        <Box>
          <Typography variant="h4">Avisos preventivos</Typography>
          <Typography color="text.secondary">Reglas auditables, evidencia clínica y explicaciones apoyadas por VetIA.</Typography>
        </Box>
        {user?.role === 'clinic' && (
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ width: { xs: '100%', md: 'auto' } }}>
            <Button variant="outlined" startIcon={<RefreshRoundedIcon />} disabled={working} onClick={() => void rebuild(false)}>
              Solo recalcular
            </Button>
            <Button variant="contained" startIcon={working ? <CircularProgress size={18} color="inherit" /> : <FactCheckRoundedIcon />} disabled={working} onClick={() => void rebuild(true)}>
              Recalcular y enriquecer
            </Button>
          </Stack>
        )}
      </Box>

      {message && <Alert severity="success" onClose={() => setMessage('')}>{message}</Alert>}
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}

      {stats && (
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: 'repeat(2,1fr)', md: 'repeat(5,1fr)' } }}>
          {[
            ['Activas', stats.active], ['Nuevas', stats.new], ['Revisadas', stats.reviewed],
            ['Resueltas', stats.resolved], ['Recurrentes', stats.recurrent]
          ].map(([label, value]) => (
            <Card key={String(label)}><CardContent><Typography color="text.secondary">{label}</Typography><Typography variant="h4">{value}</Typography></CardContent></Card>
          ))}
        </Box>
      )}

      <Card><CardContent>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2,1fr)', xl: 'repeat(5,1fr)' } }}>
          <FormControl size="small"><InputLabel>Estado</InputLabel><Select label="Estado" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <MenuItem value="active">Activas</MenuItem><MenuItem value="">Todas</MenuItem>
            <MenuItem value="new">Nuevas</MenuItem><MenuItem value="reviewed">Revisadas</MenuItem>
            <MenuItem value="resolved">Resueltas</MenuItem><MenuItem value="dismissed">Descartadas</MenuItem>
          </Select></FormControl>
          <FormControl size="small"><InputLabel>Severidad</InputLabel><Select label="Severidad" value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
            <MenuItem value="">Todas</MenuItem><MenuItem value="high">Alta</MenuItem><MenuItem value="medium">Media</MenuItem><MenuItem value="low">Baja</MenuItem><MenuItem value="info">Informativa</MenuItem>
          </Select></FormControl>
          <FormControl size="small"><InputLabel>Especie</InputLabel><Select label="Especie" value={speciesFilter} onChange={(event) => setSpeciesFilter(event.target.value)}>
            <MenuItem value="">Todas</MenuItem><MenuItem value="dog">Perros</MenuItem><MenuItem value="cat">Gatos</MenuItem>
          </Select></FormControl>
          <FormControl size="small"><InputLabel>Categoría</InputLabel><Select label="Categoría" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
            <MenuItem value="">Todas</MenuItem>{categories.map((category) => <MenuItem value={category} key={category}>{category}</MenuItem>)}
          </Select></FormControl>
          <TextField size="small" label="Buscar mascota" value={search} onChange={(event) => setSearch(event.target.value)} />
        </Box>
      </CardContent></Card>

      {loading ? <Box sx={{ display: 'grid', placeItems: 'center', py: 8 }}><CircularProgress /></Box> : alerts.length === 0 ? (
        <Alert severity="info">No hay avisos que coincidan con los filtros.</Alert>
      ) : (
        <Stack spacing={2}>
          {alerts.map((item) => {
            const ragSources = Array.isArray(item.evidence.rag_sources) ? item.evidence.rag_sources as Array<{ title?: string; source?: string; score?: number }> : []
            return (
              <Card key={item.id} sx={{ borderLeft: 6, borderColor: item.severity === 'high' ? 'error.main' : item.severity === 'medium' ? 'warning.main' : 'info.main' }}>
                <CardContent>
                  <Stack spacing={2}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                      <Box>
                        <Typography variant="h6">{item.title}</Typography>
                        <Typography color="text.secondary">
                          <Link component="button" onClick={() => navigate(`/pets/${item.pet_id}`)}>{item.pet_name}</Link>
                          {' · '}{item.breed || 'Raza no indicada'}
                        </Typography>
                      </Box>
                      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        <Chip label={severityLabels[item.severity]} color={item.severity === 'high' ? 'error' : item.severity === 'medium' ? 'warning' : 'info'} />
                        <Chip label={statusLabels[item.status]} variant="outlined" />
                        {item.occurrence_count > 1 && <Chip label={`${item.occurrence_count} detecciones`} color="secondary" variant="outlined" />}
                      </Stack>
                    </Box>
                    <Typography>{item.description}</Typography>
                    {item.llm_explanation && <Alert severity="info"><Typography fontWeight={800}>Explicación de VetIA</Typography><Typography sx={{ whiteSpace: 'pre-wrap' }}>{item.llm_explanation}</Typography></Alert>}
                    <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' } }}>
                      <Box>
                        <Typography fontWeight={800}>Evidencia de la regla</Typography>
                        <Box component="pre" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 13, bgcolor: 'grey.50', p: 1.5, borderRadius: 2, maxHeight: 240, overflow: 'auto' }}>
                          {evidenceLines(item.evidence).join('\n')}
                        </Box>
                      </Box>
                      <Box>
                        <Typography fontWeight={800}>Fuente y trazabilidad</Typography>
                        <Typography variant="body2">Regla: {item.rule_code} · v{item.rule?.version || 1}</Typography>
                        <Typography variant="body2">Fuente: {item.rule?.source || 'Fuente no indicada'}</Typography>
                        {item.rule?.source_url && <Link href={item.rule.source_url} target="_blank" rel="noreferrer">Abrir fuente</Link>}
                        <Typography variant="body2" sx={{ mt: 1 }}>Última evaluación: {item.last_evaluated_at ? new Date(item.last_evaluated_at).toLocaleString() : 'No disponible'}</Typography>
                        {ragSources.length > 0 && <Typography variant="body2" sx={{ mt: 1 }}>{ragSources.length} fragmentos usados por VetIA.</Typography>}
                      </Box>
                    </Box>
                    {item.review_notes && <Alert severity="success">Nota de revisión: {item.review_notes}</Alert>}
                    {item.resolution_reason && <Alert severity="warning">Cierre: {item.resolution_reason}</Alert>}
                    <Divider />
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="caption" color="text.secondary">
                        Creado {new Date(item.generated_at).toLocaleString()} · {item.history.length} cambios registrados
                      </Typography>
                      {user?.role === 'clinic' && <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        {item.status !== 'reviewed' && item.status !== 'resolved' && item.status !== 'dismissed' && <Button size="small" startIcon={<FactCheckRoundedIcon />} onClick={() => openAction(item, 'reviewed')}>Revisar</Button>}
                        {item.status !== 'resolved' && <Button size="small" color="success" startIcon={<DoneAllRoundedIcon />} onClick={() => openAction(item, 'resolved')}>Resolver</Button>}
                        {item.status !== 'dismissed' && <Button size="small" color="warning" startIcon={<CancelRoundedIcon />} onClick={() => openAction(item, 'dismissed')}>Descartar</Button>}
                        {(item.status === 'resolved' || item.status === 'dismissed') && <Button size="small" startIcon={<ReplayRoundedIcon />} onClick={() => openAction(item, 'new')}>Reabrir</Button>}
                      </Stack>}
                    </Box>
                  </Stack>
                </CardContent>
              </Card>
            )
          })}
        </Stack>
      )}

      <Dialog open={Boolean(selected)} onClose={() => !working && setSelected(null)} fullWidth maxWidth="sm">
        <DialogTitle>{action === 'reviewed' ? 'Marcar como revisada' : action === 'resolved' ? 'Resolver aviso' : action === 'dismissed' ? 'Descartar aviso' : 'Reabrir aviso'}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Alert severity={action === 'dismissed' ? 'warning' : 'info'} icon={<WarningAmberRoundedIcon />}>
              {selected?.pet_name}: {selected?.title}
            </Alert>
            <TextField
              label={action === 'resolved' || action === 'dismissed' ? 'Motivo obligatorio' : 'Nota de revisión'}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              multiline minRows={4} fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelected(null)} disabled={working}>Cancelar</Button>
          <Button variant="contained" onClick={() => void submitAction()} disabled={working || ((action === 'resolved' || action === 'dismissed') && !notes.trim())}>Guardar</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  )
}
