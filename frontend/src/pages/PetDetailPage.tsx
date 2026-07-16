import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog,
  DialogActions, DialogContent, DialogTitle, Divider, LinearProgress, List,
  ListItem, ListItemText, MenuItem, Stack, TextField, Typography
} from '@mui/material'
import AddCircleRoundedIcon from '@mui/icons-material/AddCircleRounded'
import AutorenewRoundedIcon from '@mui/icons-material/AutorenewRounded'
import CancelRoundedIcon from '@mui/icons-material/CancelRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import ErrorOutlineRoundedIcon from '@mui/icons-material/ErrorOutlineRounded'
import PaymentsRoundedIcon from '@mui/icons-material/PaymentsRounded'
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded'
import SmartToyRoundedIcon from '@mui/icons-material/SmartToyRounded'
import SwapHorizRoundedIcon from '@mui/icons-material/SwapHorizRounded'
import { Link as RouterLink, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { HealthPlan, PetDetail, Subscription } from '../types'

const serviceStatusLabels: Record<string, string> = {
  completed: 'Realizado', pending: 'Pendiente', upcoming: 'Proximo', overdue: 'Vencido',
  not_applicable: 'Incluido', cancelled: 'Cancelado'
}

const planStatusLabels: Record<string, string> = {
  active: 'Activo', expiring: 'Proximo a vencer', expired: 'Vencido',
  scheduled: 'Programado', cancelled: 'Cancelado'
}

const currency = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })
const today = () => new Date().toISOString().slice(0, 10)

function addOneDay(value: string) {
  const date = new Date(`${value}T12:00:00`)
  date.setDate(date.getDate() + 1)
  return date.toISOString().slice(0, 10)
}

function serviceStatusIcon(status: string) {
  if (status === 'completed') return <CheckCircleRoundedIcon color="success" />
  if (status === 'overdue') return <ErrorOutlineRoundedIcon color="error" />
  if (status === 'cancelled') return <CancelRoundedIcon color="disabled" />
  return <ScheduleRoundedIcon color="warning" />
}

function planStatusColor(status: string): 'success' | 'warning' | 'error' | 'info' | 'default' {
  if (status === 'active') return 'success'
  if (status === 'expiring' || status === 'scheduled') return 'warning'
  if (status === 'cancelled') return 'error'
  return 'default'
}

type PlanAction = 'assign' | 'change' | 'renew'

export function PetDetailPage() {
  const { petId } = useParams()
  const { user } = useAuth()
  const [pet, setPet] = useState<PetDetail | null>(null)
  const [plans, setPlans] = useState<HealthPlan[]>([])
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [updatingService, setUpdatingService] = useState<string | null>(null)
  const [updatingInstallment, setUpdatingInstallment] = useState<string | null>(null)
  const [paymentOpen, setPaymentOpen] = useState(false)
  const [paymentMode, setPaymentMode] = useState<'single' | 'installments'>('single')
  const [installmentsTotal, setInstallmentsTotal] = useState(12)
  const [installmentsPaid, setInstallmentsPaid] = useState(0)
  const [savingPayment, setSavingPayment] = useState(false)

  const [planAction, setPlanAction] = useState<PlanAction | null>(null)
  const [selectedPlanId, setSelectedPlanId] = useState('')
  const [planStartDate, setPlanStartDate] = useState(today())
  const [savingPlan, setSavingPlan] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [cancelDate, setCancelDate] = useState(today())
  const [cancelReason, setCancelReason] = useState('Baja solicitada por el cliente.')
  const [savingCancellation, setSavingCancellation] = useState(false)
  const [requestingRenewal, setRequestingRenewal] = useState(false)
  const [eventOpen, setEventOpen] = useState(false)
  const [eventDate, setEventDate] = useState(new Date().toISOString().slice(0, 16))
  const [eventType, setEventType] = useState('consultation')
  const [eventTitle, setEventTitle] = useState('')
  const [eventDescription, setEventDescription] = useState('')
  const [eventDiagnosis, setEventDiagnosis] = useState('')
  const [eventTreatment, setEventTreatment] = useState('')
  const [eventWeight, setEventWeight] = useState('')
  const [eventVisible, setEventVisible] = useState('true')
  const [savingEvent, setSavingEvent] = useState(false)

  const canEdit = user?.role === 'clinic'

  const loadPet = useCallback(() => {
    setError('')
    return api.get<PetDetail>(`/pets/${petId}`)
      .then((response) => setPet(response.data))
      .catch(() => setError('No se pudo cargar la ficha de la mascota.'))
  }, [petId])

  useEffect(() => {
    void loadPet()
    api.get<HealthPlan[]>('/plans').then((response) => setPlans(response.data)).catch(() => setError('No se pudo cargar el catalogo de planes.'))
  }, [loadPet])

  const speciesPlans = useMemo(
    () => plans.filter((plan) => plan.species === pet?.species),
    [plans, pet?.species]
  )

  const completeService = async (serviceId: string) => {
    setUpdatingService(serviceId)
    setError('')
    try {
      await api.patch(`/plans/services/${serviceId}/complete`, {
        completed_date: today(),
        notes: 'Prestacion registrada desde el portal de GamuCare AI.'
      })
      await loadPet()
    } catch {
      setError('No se pudo actualizar la prestacion.')
    } finally {
      setUpdatingService(null)
    }
  }

  const updateInstallment = async (installmentId: string, installmentStatus: 'paid' | 'pending') => {
    if (!pet?.subscription) return
    setUpdatingInstallment(installmentId)
    setError('')
    try {
      await api.patch(`/plans/subscriptions/${pet.subscription.id}/installments/${installmentId}`, {
        status: installmentStatus,
        notes: installmentStatus === 'paid' ? 'Cobro registrado desde GamuCare AI.' : 'Correccion manual del estado de la cuota.'
      })
      setSuccess(installmentStatus === 'paid' ? 'La cuota se ha marcado como pagada.' : 'El pago de la cuota se ha corregido.')
      await loadPet()
    } catch {
      setError('No se pudo actualizar la cuota.')
    } finally {
      setUpdatingInstallment(null)
    }
  }

  const saveClinicalEvent = async () => {
    if (!pet || !eventTitle.trim() || !eventDescription.trim()) return
    setSavingEvent(true)
    setError('')
    try {
      await api.post(`/pets/${pet.id}/clinical-events`, {
        event_date: new Date(eventDate).toISOString(),
        event_type: eventType,
        title: eventTitle.trim(),
        description: eventDescription.trim(),
        diagnosis: eventDiagnosis.trim() || null,
        treatment: eventTreatment.trim() || null,
        weight_kg: eventWeight ? Number(eventWeight) : null,
        visible_to_owner: eventVisible === 'true'
      })
      setEventOpen(false)
      setEventTitle('')
      setEventDescription('')
      setEventDiagnosis('')
      setEventTreatment('')
      setEventWeight('')
      setSuccess('Evento clínico guardado. Los avisos se recalcularán en segundo plano.')
      await loadPet()
    } catch {
      setError('No se pudo guardar el evento clínico.')
    } finally {
      setSavingEvent(false)
    }
  }

  const openPayment = () => {
    if (!pet?.subscription) return
    setPaymentMode(pet.subscription.payment_mode)
    setInstallmentsTotal(pet.subscription.installments_total)
    setInstallmentsPaid(pet.subscription.installments_paid)
    setPaymentOpen(true)
  }

  const savePayment = async () => {
    if (!pet?.subscription) return
    setSavingPayment(true)
    setError('')
    try {
      await api.patch(`/plans/subscriptions/${pet.subscription.id}/payment`, {
        payment_mode: paymentMode,
        installments_total: paymentMode === 'single' ? 1 : installmentsTotal,
        installments_paid: paymentMode === 'single' ? 1 : installmentsPaid
      })
      setPaymentOpen(false)
      setSuccess('El estado del pago se ha actualizado.')
      await loadPet()
    } catch {
      setError('No se pudo actualizar el estado del pago. Revisa el numero de cuotas.')
    } finally {
      setSavingPayment(false)
    }
  }

  const openPlanDialog = (action: PlanAction) => {
    if (!pet) return
    const current = pet.subscription
    setPlanAction(action)
    setSelectedPlanId(
      action === 'assign'
        ? speciesPlans[0]?.id || ''
        : current?.health_plan_id || speciesPlans[0]?.id || ''
    )
    setPlanStartDate(
      action === 'renew' && current ? addOneDay(current.end_date)
        : action === 'change' && current?.status === 'scheduled' ? current.start_date
          : today()
    )
    setPaymentMode(action === 'assign' ? 'single' : current?.payment_mode || 'single')
    setInstallmentsTotal(action === 'assign' ? 12 : current?.installments_total || 12)
    setInstallmentsPaid(action === 'renew' ? 0 : action === 'assign' ? 1 : current?.installments_paid || 0)
  }

  const savePlanAction = async () => {
    if (!pet || !planAction || !selectedPlanId) return
    setSavingPlan(true)
    setError('')
    try {
      const payment = {
        payment_mode: paymentMode,
        installments_total: paymentMode === 'single' ? 1 : installmentsTotal,
        installments_paid: paymentMode === 'single' ? 1 : installmentsPaid
      }
      if (planAction === 'assign') {
        await api.post('/plans/subscriptions', {
          pet_id: pet.id,
          health_plan_id: selectedPlanId,
          start_date: planStartDate,
          ...payment
        })
      } else if (planAction === 'change' && pet.subscription) {
        await api.post(`/plans/subscriptions/${pet.subscription.id}/change`, {
          health_plan_id: selectedPlanId,
          effective_date: planStartDate,
          reason: 'Cambio de plan registrado desde la ficha de la mascota.',
          ...payment
        })
      } else if (planAction === 'renew' && pet.subscription) {
        await api.post(`/plans/subscriptions/${pet.subscription.id}/renew`, {
          health_plan_id: selectedPlanId,
          start_date: planStartDate,
          ...payment
        })
      }
      setPlanAction(null)
      setSuccess(planAction === 'assign' ? 'Plan asignado correctamente.' : planAction === 'change' ? 'El cambio de plan se ha registrado.' : 'La renovacion ha quedado programada.')
      await loadPet()
    } catch {
      setError('No se pudo completar la operacion del plan. Revisa las fechas, la especie y si ya existe otra suscripcion.')
    } finally {
      setSavingPlan(false)
    }
  }

  const cancelPlan = async () => {
    if (!pet?.subscription) return
    setSavingCancellation(true)
    setError('')
    try {
      await api.post(`/plans/subscriptions/${pet.subscription.id}/cancel`, {
        cancellation_date: cancelDate,
        reason: cancelReason
      })
      setCancelOpen(false)
      setSuccess('El plan se ha cancelado y sus prestaciones pendientes han quedado anuladas.')
      await loadPet()
    } catch {
      setError('No se pudo cancelar el plan. Revisa la fecha y el motivo.')
    } finally {
      setSavingCancellation(false)
    }
  }

  const requestRenewal = async () => {
    if (!pet?.subscription) return
    setRequestingRenewal(true)
    setError('')
    try {
      await api.post(`/plans/subscriptions/${pet.subscription.id}/renewal-request`, {
        health_plan_id: pet.subscription.health_plan_id,
        payment_mode: pet.subscription.payment_mode,
        installments_total: pet.subscription.installments_total,
        notes: 'Solicitud enviada por el propietario desde GamuCare AI.'
      })
      setSuccess('La solicitud de renovacion se ha enviado a la clinica.')
      await loadPet()
    } catch {
      setError('No se pudo solicitar la renovacion. Puede que aun no este dentro del periodo de 90 dias o ya exista una solicitud.')
    } finally {
      setRequestingRenewal(false)
    }
  }

  if (error && !pet) return <Alert severity="error">{error}</Alert>
  if (!pet) return <Box sx={{ display: 'grid', placeItems: 'center', minHeight: 300 }}><CircularProgress /></Box>

  const subscription = pet.subscription
  const openSubscription = subscription && ['active', 'expiring', 'scheduled'].includes(subscription.status)
  const daysToEnd = subscription ? Math.ceil((new Date(`${subscription.end_date}T23:59:59`).getTime() - Date.now()) / 86400000) : 999
  const canRequestRenewal = user?.role === 'owner' && subscription && subscription.status !== 'cancelled' && subscription.renewal_status === 'not_requested' && daysToEnd <= 90
  const paymentPercentage = subscription
    ? Math.round((subscription.installments_paid / Math.max(1, subscription.installments_total)) * 100)
    : 0

  return (
    <Stack spacing={3}>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert severity="success" onClose={() => setSuccess('')}>{success}</Alert>}
      <Box>
        <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={1}>
          <Box><Typography variant="h4">{pet.name}</Typography><Typography color="text.secondary">{pet.breed} · {pet.species === 'dog' ? 'Perro' : 'Gato'}</Typography></Box>
          <Stack direction={{ xs: 'column', sm: 'row' }} gap={1} alignItems={{ sm: 'center' }}>
            <Button component={RouterLink} to={`/chat?pet_id=${pet.id}`} variant="outlined" startIcon={<SmartToyRoundedIcon />}>Preguntar al asistente</Button>
            <Chip color="primary" label={`${Number(pet.weight_kg).toFixed(1)} kg`} />
            {!pet.is_active && <Chip color="warning" label="Baja" />}
          </Stack>
        </Stack>
      </Box>

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '1fr 1.5fr' } }}>
        <Card><CardContent>
          <Typography variant="h6">Ficha</Typography>
          <List dense>
            <ListItem disableGutters><ListItemText primary="Propietario" secondary={`${pet.owner.first_name} ${pet.owner.last_name}`} /></ListItem>
            <ListItem disableGutters><ListItemText primary="Nacimiento" secondary={new Date(pet.birth_date).toLocaleDateString('es-ES')} /></ListItem>
            <ListItem disableGutters><ListItemText primary="Microchip" secondary={pet.microchip || 'No registrado'} /></ListItem>
            <ListItem disableGutters><ListItemText primary="Alergias" secondary={pet.allergies || 'Sin alergias registradas'} /></ListItem>
            <ListItem disableGutters><ListItemText primary="Antecedentes" secondary={pet.chronic_conditions || 'Sin antecedentes relevantes'} /></ListItem>
          </List>
        </CardContent></Card>

        <Card><CardContent>
          <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2}>
            <Box>
              <Typography variant="h6">Plan de salud</Typography>
              {subscription ? <>
                <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap" sx={{ mt: 1 }}>
                  <Typography variant="h5" color="primary.main">{subscription.plan_name}</Typography>
                  <Chip size="small" color={planStatusColor(subscription.status)} label={planStatusLabels[subscription.status] || subscription.status} />
                </Stack>
                <Typography color="text.secondary">Vigencia: {new Date(subscription.start_date).toLocaleDateString('es-ES')} - {new Date(subscription.end_date).toLocaleDateString('es-ES')}</Typography>
                {subscription.cancellation_reason && <Typography color="error.main" variant="body2" sx={{ mt: 1 }}>Motivo de baja: {subscription.cancellation_reason}</Typography>}
              </> : <Alert severity="info" sx={{ mt: 2 }}>Esta mascota no tiene un plan de salud.</Alert>}
            </Box>
            {canEdit && <Stack direction={{ xs: 'column', sm: 'row' }} gap={1} alignItems="flex-start">
              {!openSubscription && !pet.upcoming_subscription && <Button variant="contained" onClick={() => openPlanDialog('assign')}>Asignar plan</Button>}
              {openSubscription && <>
                <Button variant="outlined" startIcon={<SwapHorizRoundedIcon />} onClick={() => openPlanDialog('change')}>Cambiar</Button>
                {!pet.upcoming_subscription && <Button variant="outlined" startIcon={<AutorenewRoundedIcon />} onClick={() => openPlanDialog('renew')}>Renovar</Button>}
                <Button color="error" startIcon={<CancelRoundedIcon />} onClick={() => { setCancelDate(subscription?.status === 'scheduled' ? subscription.start_date : today()); setCancelOpen(true) }}>Cancelar</Button>
              </>}
              {!openSubscription && subscription && subscription.status === 'expired' && !pet.upcoming_subscription && <Button variant="contained" startIcon={<AutorenewRoundedIcon />} onClick={() => openPlanDialog('renew')}>Renovar plan</Button>}
            </Stack>}
          </Stack>
          {subscription && <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 3 }}>
            <LinearProgress variant="determinate" value={subscription.completion_percentage} sx={{ flex: 1, height: 12, borderRadius: 8 }} />
            <Typography fontWeight={800}>{subscription.completion_percentage}%</Typography>
          </Box>}
          {canRequestRenewal && <Button sx={{ mt: 2 }} variant="contained" startIcon={<AutorenewRoundedIcon />} disabled={requestingRenewal} onClick={() => void requestRenewal()}>
            {requestingRenewal ? 'Enviando...' : 'Solicitar renovacion'}
          </Button>}
          {subscription?.renewal_status === 'requested' && <Alert severity="info" sx={{ mt: 2 }}>La solicitud de renovacion esta pendiente de revision por la clinica.</Alert>}
          {subscription?.renewal_status === 'renewed' && <Alert severity="success" sx={{ mt: 2 }}>La renovacion ya ha sido gestionada.</Alert>}
        </CardContent></Card>
      </Box>

      {pet.upcoming_subscription && <Card><CardContent>
        <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2}>
          <Box>
            <Typography variant="overline" color="primary.main">Proximo plan programado</Typography>
            <Typography variant="h5">{pet.upcoming_subscription.plan_name}</Typography>
            <Typography color="text.secondary">Comienza el {new Date(pet.upcoming_subscription.start_date).toLocaleDateString('es-ES')} y finaliza el {new Date(pet.upcoming_subscription.end_date).toLocaleDateString('es-ES')}.</Typography>
          </Box>
          <Chip color="warning" label="Programado" />
        </Stack>
      </CardContent></Card>}

      {subscription && <Card><CardContent>
        <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2}>
          <Box>
            <Stack direction="row" gap={1} alignItems="center"><PaymentsRoundedIcon color="primary" /><Typography variant="h6">Estado del pago</Typography></Stack>
            <Stack direction="row" gap={1} flexWrap="wrap" sx={{ mt: 1.5 }}>
              <Chip color={subscription.payment_status === 'paid' ? 'success' : 'warning'} label={subscription.payment_status === 'paid' ? 'Pagado' : `Pago a plazos · ${subscription.installments_paid}/${subscription.installments_total}`} />
              <Chip variant="outlined" label={subscription.payment_mode === 'single' ? 'Pago completo' : `${currency.format(Number(subscription.installment_amount))} por cuota`} />
            </Stack>
          </Box>
          {canEdit && subscription.status !== 'cancelled' && <Button variant="outlined" onClick={openPayment}>Actualizar pago</Button>}
        </Stack>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(3, 1fr)' }, mt: 3 }}>
          <Box><Typography variant="caption" color="text.secondary">Importe total</Typography><Typography variant="h6">{currency.format(Number(subscription.total_amount))}</Typography></Box>
          <Box><Typography variant="caption" color="text.secondary">Pagado</Typography><Typography variant="h6" color="success.main">{currency.format(Number(subscription.amount_paid))}</Typography></Box>
          <Box><Typography variant="caption" color="text.secondary">Pendiente</Typography><Typography variant="h6" color={Number(subscription.amount_remaining) > 0 ? 'warning.main' : 'success.main'}>{currency.format(Number(subscription.amount_remaining))}</Typography></Box>
        </Box>
        {subscription.payment_mode === 'installments' && <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 2 }}>
          <LinearProgress variant="determinate" value={paymentPercentage} color={paymentPercentage === 100 ? 'success' : 'primary'} sx={{ flex: 1, height: 10, borderRadius: 8 }} />
          <Typography fontWeight={800}>{paymentPercentage}%</Typography>
        </Box>}
        {subscription.installments.length > 0 && <>
          <Divider sx={{ my: 2.5 }} />
          <Typography variant="subtitle1" fontWeight={800}>Detalle de cuotas</Typography>
          <List dense>
            {subscription.installments.map((installment, index) => <Box key={installment.id}>
              <ListItem disableGutters>
                <ListItemText
                  primary={`Cuota ${installment.installment_number} · ${currency.format(Number(installment.amount))}`}
                  secondary={`Vencimiento: ${new Date(installment.due_date).toLocaleDateString('es-ES')}${installment.paid_at ? ` · Pagada: ${new Date(installment.paid_at).toLocaleDateString('es-ES')}` : ''}`}
                />
                <Stack direction={{ xs: 'column', sm: 'row' }} gap={1} alignItems="flex-end">
                  <Chip
                    size="small"
                    color={installment.status === 'paid' ? 'success' : installment.status === 'overdue' ? 'error' : installment.status === 'cancelled' ? 'default' : 'warning'}
                    label={installment.status === 'paid' ? 'Pagada' : installment.status === 'overdue' ? 'Vencida' : installment.status === 'cancelled' ? 'Cancelada' : 'Pendiente'}
                  />
                  {canEdit && installment.status !== 'cancelled' && <Button
                    size="small"
                    disabled={updatingInstallment === installment.id}
                    onClick={() => void updateInstallment(installment.id, installment.status === 'paid' ? 'pending' : 'paid')}
                  >
                    {updatingInstallment === installment.id ? 'Guardando...' : installment.status === 'paid' ? 'Corregir' : 'Marcar pagada'}
                  </Button>}
                </Stack>
              </ListItem>
              {index < subscription.installments.length - 1 && <Divider />}
            </Box>)}
          </List>
        </>}
      </CardContent></Card>}

      {pet.alerts.length > 0 && <Card><CardContent>
        <Typography variant="h6" sx={{ mb: 2 }}>Avisos preventivos</Typography>
        <Stack spacing={1.5}>{pet.alerts.map((alert) => {
          const ragSources = Array.isArray(alert.evidence?.rag_sources) ? alert.evidence.rag_sources as Array<{ title?: string; pet_name?: string; breed?: string; score?: number }> : []
          return <Alert key={alert.id} severity={alert.severity === 'high' ? 'error' : alert.severity === 'medium' ? 'warning' : 'info'}>
            <Typography fontWeight={800}>{alert.title}</Typography><Typography variant="body2">{alert.description}</Typography>
            {alert.llm_explanation && <Box sx={{ mt: 1.5, p: 1.5, borderRadius: 2, bgcolor: 'rgba(255,255,255,.6)' }}>
              <Typography variant="caption" fontWeight={800}>Explicacion apoyada por VetIA</Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mt: 0.5 }}>{alert.llm_explanation}</Typography>
              {ragSources.length > 0 && <Stack direction="row" gap={0.75} flexWrap="wrap" sx={{ mt: 1 }}>{ragSources.slice(0, 5).map((source, index) => <Chip key={index} size="small" variant="outlined" label={`${source.pet_name || source.title || 'Fuente'}${source.breed ? ` · ${source.breed}` : ''}`} />)}</Stack>}
            </Box>}
          </Alert>
        })}</Stack>
      </CardContent></Card>}

      {subscription && <Card><CardContent>
        <Typography variant="h6">Prestaciones del plan</Typography>
        <List>{subscription.services.map((service, index) => <Box key={service.id}>
          <ListItem disableGutters alignItems="flex-start">
            <Box sx={{ mr: 2, mt: 0.5 }}>{serviceStatusIcon(service.status)}</Box>
            <ListItemText primary={service.name} secondary={service.completed_date ? `Realizado: ${new Date(service.completed_date).toLocaleDateString('es-ES')}` : service.scheduled_date ? `Previsto: ${new Date(service.scheduled_date).toLocaleDateString('es-ES')}` : service.notes || 'Disponible durante la vigencia'} />
            <Stack direction={{ xs: 'column', sm: 'row' }} gap={1} alignItems="flex-end" sx={{ ml: 1 }}>
              <Chip size="small" label={serviceStatusLabels[service.status] || service.status} color={service.status === 'completed' ? 'success' : service.status === 'overdue' ? 'error' : 'default'} />
              {canEdit && ['pending', 'upcoming', 'overdue'].includes(service.status) && subscription.status !== 'cancelled' && <Button size="small" variant="outlined" disabled={updatingService === service.id} onClick={() => void completeService(service.id)}>{updatingService === service.id ? 'Guardando...' : 'Marcar realizado'}</Button>}
            </Stack>
          </ListItem>
          {index < subscription.services.length - 1 && <Divider />}
        </Box>)}</List>
      </CardContent></Card>}

      <Card><CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, alignItems: 'center' }}>
          <Typography variant="h6">Historial clínico</Typography>
          {canEdit && <Button startIcon={<AddCircleRoundedIcon />} onClick={() => setEventOpen(true)}>Añadir evento</Button>}
        </Box>
        <List>{pet.clinical_events.map((event, index) => <Box key={event.id}><ListItem disableGutters alignItems="flex-start"><ListItemText primary={event.title} secondary={`${new Date(event.event_date).toLocaleDateString('es-ES')} · ${event.description}`} /></ListItem>{index < pet.clinical_events.length - 1 && <Divider />}</Box>)}</List>
      </CardContent></Card>

      <Dialog open={eventOpen} onClose={() => !savingEvent && setEventOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>Añadir evento clínico</DialogTitle>
        <DialogContent><Stack spacing={2} sx={{ mt: 1 }}>
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
            <TextField type="datetime-local" label="Fecha" value={eventDate} onChange={(event) => setEventDate(event.target.value)} InputLabelProps={{ shrink: true }} />
            <TextField select label="Tipo" value={eventType} onChange={(event) => setEventType(event.target.value)}>
              <MenuItem value="consultation">Consulta</MenuItem><MenuItem value="vaccination">Vacunación</MenuItem>
              <MenuItem value="laboratory">Analítica</MenuItem><MenuItem value="treatment">Tratamiento</MenuItem>
              <MenuItem value="follow_up">Seguimiento</MenuItem><MenuItem value="other">Otro</MenuItem>
            </TextField>
          </Box>
          <TextField label="Título" value={eventTitle} onChange={(event) => setEventTitle(event.target.value)} />
          <TextField label="Descripción" value={eventDescription} onChange={(event) => setEventDescription(event.target.value)} multiline minRows={3} />
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
            <TextField label="Diagnóstico registrado" value={eventDiagnosis} onChange={(event) => setEventDiagnosis(event.target.value)} />
            <TextField label="Tratamiento registrado" value={eventTreatment} onChange={(event) => setEventTreatment(event.target.value)} />
            <TextField type="number" label="Peso (kg)" value={eventWeight} onChange={(event) => setEventWeight(event.target.value)} inputProps={{ min: 0.1, step: 0.1 }} />
            <TextField select label="Visible para el propietario" value={eventVisible} onChange={(event) => setEventVisible(event.target.value)}>
              <MenuItem value="true">Sí</MenuItem><MenuItem value="false">No, nota interna</MenuItem>
            </TextField>
          </Box>
          <Alert severity="info">Al guardar, la ficha se reindexa en Qdrant y los avisos preventivos se vuelven a evaluar.</Alert>
        </Stack></DialogContent>
        <DialogActions><Button onClick={() => setEventOpen(false)} disabled={savingEvent}>Cancelar</Button><Button variant="contained" onClick={() => void saveClinicalEvent()} disabled={savingEvent || !eventTitle.trim() || !eventDescription.trim()}>{savingEvent ? 'Guardando...' : 'Guardar evento'}</Button></DialogActions>
      </Dialog>

      <Dialog open={paymentOpen} onClose={() => !savingPayment && setPaymentOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Actualizar estado del pago</DialogTitle>
        <DialogContent><PaymentFields paymentMode={paymentMode} setPaymentMode={setPaymentMode} installmentsTotal={installmentsTotal} setInstallmentsTotal={setInstallmentsTotal} installmentsPaid={installmentsPaid} setInstallmentsPaid={setInstallmentsPaid} /></DialogContent>
        <DialogActions><Button onClick={() => setPaymentOpen(false)} disabled={savingPayment}>Cancelar</Button><Button variant="contained" onClick={() => void savePayment()} disabled={savingPayment}>{savingPayment ? 'Guardando...' : 'Guardar'}</Button></DialogActions>
      </Dialog>

      <Dialog open={planAction !== null} onClose={() => !savingPlan && setPlanAction(null)} fullWidth maxWidth="sm">
        <DialogTitle>{planAction === 'assign' ? 'Asignar plan de salud' : planAction === 'change' ? 'Cambiar plan de salud' : 'Renovar plan de salud'}</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ mt: 1 }}>
            <TextField select label="Plan" value={selectedPlanId} onChange={(event) => setSelectedPlanId(event.target.value)}>
              {speciesPlans.map((plan) => <MenuItem key={plan.id} value={plan.id}>{plan.name} · {currency.format(Number(plan.price_single))}</MenuItem>)}
            </TextField>
            <TextField type="date" label={planAction === 'change' ? 'Fecha efectiva' : 'Fecha de inicio'} value={planStartDate} onChange={(event) => setPlanStartDate(event.target.value)} InputLabelProps={{ shrink: true }} />
            <PaymentFields paymentMode={paymentMode} setPaymentMode={setPaymentMode} installmentsTotal={installmentsTotal} setInstallmentsTotal={setInstallmentsTotal} installmentsPaid={installmentsPaid} setInstallmentsPaid={setInstallmentsPaid} />
            <Alert severity="info">Al asignar o renovar se generan automaticamente todas las prestaciones y sus fechas previstas. Un cambio cancela el plan anterior y conserva las prestaciones ya realizadas.</Alert>
          </Stack>
        </DialogContent>
        <DialogActions><Button onClick={() => setPlanAction(null)} disabled={savingPlan}>Cancelar</Button><Button variant="contained" onClick={() => void savePlanAction()} disabled={savingPlan || !selectedPlanId}>{savingPlan ? 'Guardando...' : 'Confirmar'}</Button></DialogActions>
      </Dialog>

      <Dialog open={cancelOpen} onClose={() => !savingCancellation && setCancelOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Cancelar plan de salud</DialogTitle>
        <DialogContent><Stack spacing={2.5} sx={{ mt: 1 }}>
          <TextField type="date" label="Fecha de baja" value={cancelDate} onChange={(event) => setCancelDate(event.target.value)} InputLabelProps={{ shrink: true }} />
          <TextField label="Motivo" value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} multiline minRows={3} />
          <Alert severity="warning">La baja no elimina el historial. Las prestaciones realizadas se conservan y las pendientes quedan canceladas.</Alert>
        </Stack></DialogContent>
        <DialogActions><Button onClick={() => setCancelOpen(false)} disabled={savingCancellation}>Volver</Button><Button color="error" variant="contained" onClick={() => void cancelPlan()} disabled={savingCancellation || cancelReason.trim().length < 3}>{savingCancellation ? 'Cancelando...' : 'Confirmar baja'}</Button></DialogActions>
      </Dialog>
    </Stack>
  )
}

interface PaymentFieldsProps {
  paymentMode: 'single' | 'installments'
  setPaymentMode: (value: 'single' | 'installments') => void
  installmentsTotal: number
  setInstallmentsTotal: (value: number) => void
  installmentsPaid: number
  setInstallmentsPaid: (value: number) => void
}

function PaymentFields({ paymentMode, setPaymentMode, installmentsTotal, setInstallmentsTotal, installmentsPaid, setInstallmentsPaid }: PaymentFieldsProps) {
  return <Stack spacing={2.5}>
    <TextField select label="Modalidad de pago" value={paymentMode} onChange={(event) => {
      const mode = event.target.value as 'single' | 'installments'
      setPaymentMode(mode)
      if (mode === 'single') { setInstallmentsTotal(1); setInstallmentsPaid(1) }
      else if (installmentsTotal < 2) { setInstallmentsTotal(12); setInstallmentsPaid(0) }
    }}>
      <MenuItem value="single">Pago completo</MenuItem>
      <MenuItem value="installments">Pago a plazos</MenuItem>
    </TextField>
    {paymentMode === 'installments' && <>
      <TextField type="number" label="Numero total de cuotas" value={installmentsTotal} inputProps={{ min: 2, max: 12 }} onChange={(event) => {
        const parsed = Number(event.target.value)
        const value = Number.isFinite(parsed) ? Math.max(2, Math.min(12, parsed)) : 2
        setInstallmentsTotal(value)
        setInstallmentsPaid(Math.min(installmentsPaid, value))
      }} />
      <TextField type="number" label="Cuotas ya pagadas" value={installmentsPaid} inputProps={{ min: 0, max: installmentsTotal }} onChange={(event) => {
        const parsed = Number(event.target.value)
        setInstallmentsPaid(Number.isFinite(parsed) ? Math.max(0, Math.min(installmentsTotal, parsed)) : 0)
      }} />
    </>}
  </Stack>
}
