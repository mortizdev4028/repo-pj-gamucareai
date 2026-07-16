import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Alert, Box, Button, Card, CardActionArea, CardContent, Chip, CircularProgress,
  FormControl, InputLabel, LinearProgress, MenuItem, Select, Stack, Typography
} from '@mui/material'
import PetsRoundedIcon from '@mui/icons-material/PetsRounded'
import HealthAndSafetyRoundedIcon from '@mui/icons-material/HealthAndSafetyRounded'
import EventBusyRoundedIcon from '@mui/icons-material/EventBusyRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import EuroRoundedIcon from '@mui/icons-material/EuroRounded'
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded'
import CalendarMonthRoundedIcon from '@mui/icons-material/CalendarMonthRounded'
import TaskAltRoundedIcon from '@mui/icons-material/TaskAltRounded'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type {
  DashboardData, DashboardRankedItem, DashboardTrendPoint, HealthPlan
} from '../types'

const money = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })
const formatMoney = (value: number | string | undefined) => money.format(Number(value || 0))
const shortDate = new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: 'short', year: 'numeric' })

const statusLabels: Record<string, string> = {
  active: 'Activo', expiring: 'Próximo a vencer', scheduled: 'Programado', expired: 'Vencido', cancelled: 'Cancelado',
  pending: 'Pendiente', upcoming: 'Próximo', overdue: 'Vencido', completed: 'Realizado', not_applicable: 'Informativo',
  new: 'Nuevo', reviewed: 'Revisado', resolved: 'Resuelto', dismissed: 'Descartado',
  high: 'Alta', medium: 'Media', low: 'Baja', info: 'Informativa'
}

function KpiCard({ label, value, detail, icon, onClick }: {
  label: string; value: string | number; detail?: string; icon: ReactNode; onClick?: () => void
}) {
  const content = (
    <CardContent sx={{ height: '100%' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2 }}>
        <Box>
          <Typography color="text.secondary" variant="body2">{label}</Typography>
          <Typography variant="h3" sx={{ mt: 0.8, fontSize: { xs: '2rem', xl: '2.45rem' } }}>{value}</Typography>
          {detail && <Typography variant="caption" color="text.secondary">{detail}</Typography>}
        </Box>
        <Box sx={{ width: 48, height: 48, flexShrink: 0, display: 'grid', placeItems: 'center', borderRadius: 3.5, bgcolor: 'primary.main', color: 'white' }}>
          {icon}
        </Box>
      </Box>
    </CardContent>
  )
  return <Card sx={{ height: '100%' }}>{onClick ? <CardActionArea onClick={onClick} sx={{ height: '100%' }}>{content}</CardActionArea> : content}</Card>
}

function TrendBars({ data, field, title, formatter }: {
  data: DashboardTrendPoint[]
  field: keyof Pick<DashboardTrendPoint, 'plans_started' | 'renewals' | 'services_completed' | 'alerts_generated' | 'amount_collected'>
  title: string
  formatter?: (value: number) => string
}) {
  const values = data.map((item) => Number(item[field]))
  const max = Math.max(...values, 1)
  return (
    <Card><CardContent>
      <Typography variant="h6">{title}</Typography>
      <Box sx={{ height: 190, display: 'flex', gap: 1, alignItems: 'flex-end', mt: 2, px: 0.5 }}>
        {data.map((item) => {
          const value = Number(item[field])
          const height = Math.max(value > 0 ? 8 : 2, value / max * 145)
          return (
            <Box key={item.month} sx={{ flex: 1, minWidth: 0, textAlign: 'center' }} title={`${item.label}: ${formatter ? formatter(value) : value}`}>
              <Typography variant="caption" fontWeight={750} sx={{ display: 'block', mb: 0.5, whiteSpace: 'nowrap' }}>
                {formatter ? formatter(value) : value}
              </Typography>
              <Box sx={{ height, borderRadius: '8px 8px 3px 3px', bgcolor: 'primary.main', opacity: value ? 0.9 : 0.16, transition: 'height .2s' }} />
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.8, whiteSpace: 'nowrap' }}>{item.label}</Typography>
            </Box>
          )
        })}
      </Box>
    </CardContent></Card>
  )
}

function Breakdown({ title, values, labels = {} }: { title: string; values: Record<string, number>; labels?: Record<string, string> }) {
  const entries = Object.entries(values).sort((a, b) => b[1] - a[1])
  const total = entries.reduce((sum, [, value]) => sum + value, 0)
  return (
    <Card><CardContent>
      <Typography variant="h6" sx={{ mb: 2 }}>{title}</Typography>
      {entries.length === 0 && <Typography color="text.secondary">No hay datos para los filtros seleccionados.</Typography>}
      <Stack spacing={1.7}>
        {entries.map(([key, value]) => (
          <Box key={key}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2">{labels[key] || statusLabels[key] || key}</Typography>
              <Typography variant="body2" fontWeight={800}>{value}</Typography>
            </Box>
            <LinearProgress variant="determinate" value={total ? value / total * 100 : 0} sx={{ height: 8, borderRadius: 6 }} />
          </Box>
        ))}
      </Stack>
    </CardContent></Card>
  )
}

function Ranking({ title, items }: { title: string; items: DashboardRankedItem[] }) {
  const max = Math.max(...items.map((item) => item.count), 1)
  return (
    <Card><CardContent>
      <Typography variant="h6" sx={{ mb: 2 }}>{title}</Typography>
      {items.length === 0 && <Typography color="text.secondary">No hay recurrencias en el periodo seleccionado.</Typography>}
      <Stack spacing={1.5}>
        {items.map((item) => (
          <Box key={item.key}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
              <Typography variant="body2" noWrap>{item.label}</Typography>
              <Typography variant="body2" fontWeight={800}>{item.count}</Typography>
            </Box>
            <LinearProgress variant="determinate" value={item.count / max * 100} sx={{ mt: 0.5, height: 7, borderRadius: 5 }} />
          </Box>
        ))}
      </Stack>
    </CardContent></Card>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [data, setData] = useState<DashboardData | null>(null)
  const [plans, setPlans] = useState<HealthPlan[]>([])
  const [months, setMonths] = useState(6)
  const [species, setSpecies] = useState('')
  const [planId, setPlanId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const params = useMemo(() => ({ months, species: species || undefined, plan_id: planId || undefined }), [months, species, planId])

  const loadDashboard = useCallback(() => {
    setLoading(true)
    setError('')
    api.get<DashboardData>('/dashboard', { params })
      .then((response) => setData(response.data))
      .catch(() => setError('No se pudo cargar el panel de control.'))
      .finally(() => setLoading(false))
  }, [params])

  useEffect(() => {
    api.get<HealthPlan[]>('/plans').then((response) => setPlans(response.data)).catch(() => undefined)
  }, [])
  useEffect(() => { loadDashboard() }, [loadDashboard])

  const exportCsv = async () => {
    const response = await api.get('/dashboard/export.csv', { params, responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `gamucare-dashboard-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }

  if (error) return <Alert severity="error" action={<Button onClick={loadDashboard}>Reintentar</Button>}>{error}</Alert>
  if (!data && loading) return <Box sx={{ display: 'grid', placeItems: 'center', minHeight: 300 }}><CircularProgress /></Box>
  if (!data) return null

  const isOwner = user?.role === 'owner'
  const filteredPlans = species ? plans.filter((plan) => plan.species === species) : plans

  return (
    <Stack spacing={3}>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: { xs: 'stretch', md: 'center' }, justifyContent: 'space-between', gap: 2 }}>
        <Box>
          <Typography variant="h4">{isOwner ? 'Salud de mis mascotas' : 'Panel de control de la clínica'}</Typography>
          <Typography color="text.secondary">
            {isOwner ? 'Planes, próximos cuidados y pagos en una sola vista.' : 'Seguimiento operativo, preventivo y económico de los planes LifeCare.'}
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<DownloadRoundedIcon />} onClick={exportCsv}>Exportar CSV</Button>
      </Box>

      <Card><CardContent>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' }, gap: 2, alignItems: 'center' }}>
          <FormControl size="small"><InputLabel>Periodo</InputLabel><Select value={months} label="Periodo" onChange={(event) => setMonths(Number(event.target.value))}>
            {[3, 6, 12, 24].map((value) => <MenuItem key={value} value={value}>Últimos {value} meses</MenuItem>)}
          </Select></FormControl>
          <FormControl size="small"><InputLabel>Especie</InputLabel><Select value={species} label="Especie" onChange={(event) => { setSpecies(event.target.value); setPlanId('') }}>
            <MenuItem value="">Todas</MenuItem><MenuItem value="dog">Perros</MenuItem><MenuItem value="cat">Gatos</MenuItem>
          </Select></FormControl>
          <FormControl size="small"><InputLabel>Plan</InputLabel><Select value={planId} label="Plan" onChange={(event) => setPlanId(event.target.value)}>
            <MenuItem value="">Todos</MenuItem>{filteredPlans.map((plan) => <MenuItem key={plan.id} value={plan.id}>{plan.name}</MenuItem>)}
          </Select></FormControl>
          <Typography variant="caption" color="text.secondary">Actualizado: {new Date(data.generated_at).toLocaleString('es-ES')}</Typography>
        </Box>
      </CardContent></Card>

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', xl: 'repeat(3, 1fr)' }, opacity: loading ? 0.55 : 1 }}>
        <KpiCard label={isOwner ? 'Mis mascotas' : 'Mascotas activas'} value={data.pets_total} icon={<PetsRoundedIcon />} onClick={() => navigate('/pets')} />
        <KpiCard label="Planes activos" value={data.plans_active} detail={`${data.plans_expiring} próximos a vencer`} icon={<HealthAndSafetyRoundedIcon />} onClick={() => navigate('/plans')} />
        <KpiCard label="Servicios vencidos" value={data.services_overdue} detail={`${data.services_pending} pendientes o próximos`} icon={<EventBusyRoundedIcon />} onClick={() => navigate('/pets')} />
        <KpiCard label="Mascotas con avisos" value={data.pets_with_alerts} icon={<WarningAmberRoundedIcon />} onClick={() => navigate(isOwner ? '/pets' : '/alerts')} />
        <KpiCard label="Importe pendiente" value={formatMoney(data.financial.amount_outstanding)} detail={`${formatMoney(data.financial.overdue_amount)} vencido`} icon={<EuroRoundedIcon />} onClick={() => navigate('/plans')} />
        <KpiCard label="Cumplimiento medio" value={`${data.completion_average}%`} detail="Prestaciones realizadas" icon={<TaskAltRoundedIcon />} onClick={() => navigate('/pets')} />
      </Box>

      {isOwner && data.owner_pets.length > 0 && (
        <Box>
          <Typography variant="h5" sx={{ mb: 2 }}>Resumen por mascota</Typography>
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, 1fr)' } }}>
            {data.owner_pets.map((pet) => (
              <Card key={pet.pet_id}><CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
                  <Box><Typography variant="h6">{pet.pet_name}</Typography><Typography color="text.secondary">{pet.breed}</Typography></Box>
                  <Chip label={pet.plan_name || 'Sin plan'} color={pet.plan_name ? 'primary' : 'default'} />
                </Box>
                <Typography variant="body2" sx={{ mt: 2 }}>Cumplimiento del plan: <strong>{pet.completion_percentage}%</strong></Typography>
                <LinearProgress variant="determinate" value={pet.completion_percentage} sx={{ height: 9, borderRadius: 6, my: 1 }} />
                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 1, mt: 2 }}>
                  <Box><Typography variant="caption" color="text.secondary">Pendientes</Typography><Typography variant="h6">{pet.services_pending}</Typography></Box>
                  <Box><Typography variant="caption" color="text.secondary">Vencidos</Typography><Typography variant="h6">{pet.services_overdue}</Typography></Box>
                  <Box><Typography variant="caption" color="text.secondary">Avisos</Typography><Typography variant="h6">{pet.active_alerts}</Typography></Box>
                </Box>
                <Typography variant="body2" sx={{ mt: 2 }}>Pendiente de pago: <strong>{formatMoney(pet.amount_remaining)}</strong></Typography>
                {pet.next_installment_date && <Typography variant="caption" color="text.secondary">Próxima cuota: {shortDate.format(new Date(pet.next_installment_date))} · {formatMoney(pet.next_installment_amount)}</Typography>}
                <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
                  <Button size="small" variant="contained" onClick={() => navigate(`/pets/${pet.pet_id}`)}>Ver ficha</Button>
                  <Button size="small" onClick={() => navigate(`/chat?pet_id=${pet.pet_id}`)}>Preguntar</Button>
                </Box>
              </CardContent></Card>
            ))}
          </Box>
        </Box>
      )}

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, 1fr)' } }}>
        <TrendBars data={data.monthly_trends} field="services_completed" title="Servicios realizados por mes" />
        <TrendBars data={data.monthly_trends} field="amount_collected" title="Cobros registrados por mes" formatter={(value) => formatMoney(value)} />
      </Box>

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: 'repeat(3, 1fr)' } }}>
        <Breakdown title="Estado de los planes" values={data.plans_by_status} />
        <Breakdown title="Estado de las prestaciones" values={data.services_by_status} />
        <Breakdown title="Avisos por severidad" values={data.alerts_by_severity} />
      </Box>

      {!isOwner && (
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, 1fr)' } }}>
          <Ranking title="Avisos preventivos más frecuentes" items={data.top_alert_rules} />
          <Ranking title="Actividad clínica recurrente" items={data.top_clinical_events} />
        </Box>
      )}

      <Card><CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}><CalendarMonthRoundedIcon color="primary" /><Typography variant="h6">Próximas acciones</Typography></Box>
        {data.upcoming_items.length === 0 && <Typography color="text.secondary">No hay actuaciones urgentes o próximas con los filtros actuales.</Typography>}
        <Stack divider={<Box sx={{ borderBottom: '1px solid', borderColor: 'divider' }} />}>
          {data.upcoming_items.map((item, index) => (
            <Box key={`${item.item_type}-${item.pet_id}-${item.due_date}-${index}`} onClick={() => navigate(item.target_url)} sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr auto auto' }, gap: 1.5, py: 1.5, cursor: 'pointer', alignItems: 'center' }}>
              <Box><Typography fontWeight={800}>{item.title}</Typography><Typography variant="body2" color="text.secondary">{item.pet_name} · {item.detail}</Typography></Box>
              <Chip size="small" label={statusLabels[item.status] || item.status} color={item.status === 'overdue' || item.severity === 'high' ? 'warning' : 'default'} />
              <Typography variant="body2" fontWeight={700}>{shortDate.format(new Date(item.due_date))}</Typography>
            </Box>
          ))}
        </Stack>
      </CardContent></Card>
    </Stack>
  )
}
