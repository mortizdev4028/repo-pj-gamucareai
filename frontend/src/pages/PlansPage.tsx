import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Divider,
  List, ListItem, ListItemText, Stack, Typography
} from '@mui/material'
import AutorenewRoundedIcon from '@mui/icons-material/AutorenewRounded'
import EventBusyRoundedIcon from '@mui/icons-material/EventBusyRounded'
import PaymentsRoundedIcon from '@mui/icons-material/PaymentsRounded'
import { Link as RouterLink } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { HealthPlan, RenewalRequestItem, SubscriptionListItem } from '../types'

const currency = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })

export function PlansPage() {
  const { user } = useAuth()
  const [plans, setPlans] = useState<HealthPlan[]>([])
  const [expiring, setExpiring] = useState<SubscriptionListItem[]>([])
  const [renewals, setRenewals] = useState<RenewalRequestItem[]>([])
  const [loading, setLoading] = useState(true)
  const [reviewing, setReviewing] = useState<string | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [plansResponse, expiringResponse, renewalResponse] = await Promise.all([
        api.get<HealthPlan[]>('/plans'),
        api.get<SubscriptionListItem[]>('/plans/subscriptions?expiring_days=45'),
        api.get<RenewalRequestItem[]>('/plans/renewal-requests?status=pending')
      ])
      setPlans(plansResponse.data)
      setExpiring(expiringResponse.data)
      setRenewals(renewalResponse.data)
    } catch {
      setError('No se pudo cargar la gestion de planes.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const reviewRenewal = async (requestId: string, decision: 'approved' | 'rejected') => {
    setReviewing(requestId)
    setError('')
    try {
      await api.patch(`/plans/renewal-requests/${requestId}`, {
        status: decision,
        notes: decision === 'approved' ? 'Renovacion aprobada desde el portal.' : 'Solicitud rechazada desde el portal.'
      })
      await load()
    } catch {
      setError('No se pudo revisar la solicitud de renovacion.')
    } finally {
      setReviewing(null)
    }
  }

  if (loading) return <Box sx={{ display: 'grid', placeItems: 'center', minHeight: 300 }}><CircularProgress /></Box>

  return (
    <Stack spacing={3}>
      {error && <Alert severity="error">{error}</Alert>}
      <Box>
        <Typography variant="h4">Planes LifeCare</Typography>
        <Typography color="text.secondary">Catalogo, vencimientos y solicitudes de renovacion.</Typography>
      </Box>

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' } }}>
        <Card><CardContent>
          <Stack direction="row" gap={1.5} alignItems="center"><EventBusyRoundedIcon color="warning" /><Box><Typography variant="h4">{expiring.length}</Typography><Typography color="text.secondary">Vencen en 45 dias</Typography></Box></Stack>
        </CardContent></Card>
        <Card><CardContent>
          <Stack direction="row" gap={1.5} alignItems="center"><AutorenewRoundedIcon color="primary" /><Box><Typography variant="h4">{renewals.length}</Typography><Typography color="text.secondary">Renovaciones pendientes</Typography></Box></Stack>
        </CardContent></Card>
        <Card><CardContent>
          <Stack direction="row" gap={1.5} alignItems="center"><PaymentsRoundedIcon color="secondary" /><Box><Typography variant="h4">{expiring.filter((item) => item.payment_status !== 'paid').length}</Typography><Typography color="text.secondary">Con importe pendiente</Typography></Box></Stack>
        </CardContent></Card>
      </Box>

      <Card><CardContent>
        <Typography variant="h6">Planes proximos a vencer</Typography>
        <Typography color="text.secondary" sx={{ mb: 1 }}>Suscripciones activas cuya fecha de fin se encuentra dentro de los proximos 45 dias.</Typography>
        {expiring.length === 0 ? <Alert severity="success">No hay planes proximos a vencer.</Alert> : <List>
          {expiring.map((item, index) => <Box key={item.id}>
            <ListItem disableGutters alignItems="flex-start">
              <ListItemText
                primary={`${item.pet_name} · ${item.plan_name}`}
                secondary={`${item.owner_name} · Finaliza el ${new Date(item.end_date).toLocaleDateString('es-ES')} · ${Math.max(0, item.days_until_expiry)} dias`}
              />
              <Stack direction={{ xs: 'column', sm: 'row' }} gap={1} alignItems="flex-end">
                <Chip size="small" color={item.payment_status === 'paid' ? 'success' : 'warning'} label={item.payment_status === 'paid' ? 'Pagado' : `Pendiente ${currency.format(Number(item.amount_remaining))}`} />
                <Button size="small" component={RouterLink} to={`/pets/${item.pet_id}`}>Abrir ficha</Button>
              </Stack>
            </ListItem>
            {index < expiring.length - 1 && <Divider />}
          </Box>)}
        </List>}
      </CardContent></Card>

      {(user?.role === 'clinic' || user?.role === 'staff') && <Card><CardContent>
        <Typography variant="h6">Solicitudes de renovacion</Typography>
        <Typography color="text.secondary" sx={{ mb: 1 }}>Peticiones enviadas desde el portal del propietario.</Typography>
        {renewals.length === 0 ? <Alert severity="info">No hay solicitudes pendientes.</Alert> : <List>
          {renewals.map((item, index) => <Box key={item.id}>
            <ListItem disableGutters alignItems="flex-start">
              <ListItemText
                primary={`${item.pet_name} · ${item.requested_plan_name || item.current_plan_name}`}
                secondary={`${item.owner_name} · ${item.payment_mode === 'installments' ? `${item.installments_total} cuotas` : 'Pago completo'}${item.notes ? ` · ${item.notes}` : ''}`}
              />
              <Stack direction={{ xs: 'column', sm: 'row' }} gap={1} alignItems="flex-end">
                <Button size="small" component={RouterLink} to={`/pets/${item.pet_id}`}>Ver mascota</Button>
                {user.role === 'clinic' && <>
                  <Button size="small" color="error" disabled={reviewing === item.id} onClick={() => void reviewRenewal(item.id, 'rejected')}>Rechazar</Button>
                  <Button size="small" variant="contained" disabled={reviewing === item.id} onClick={() => void reviewRenewal(item.id, 'approved')}>Aprobar</Button>
                </>}
              </Stack>
            </ListItem>
            {index < renewals.length - 1 && <Divider />}
          </Box>)}
        </List>}
      </CardContent></Card>}

      <Box>
        <Typography variant="h5" sx={{ mb: 2 }}>Catalogo disponible</Typography>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', xl: 'repeat(2,1fr)' } }}>
          {plans.map((plan) => <Card key={plan.id}><CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={2}>
              <Box><Typography variant="h5">{plan.name}</Typography><Typography color="text.secondary">{plan.description}</Typography></Box>
              <Chip color={plan.lifecycle === 'total' ? 'warning' : plan.lifecycle === 'baby' ? 'secondary' : 'primary'} label={plan.species === 'dog' ? 'Perros' : 'Gatos'} />
            </Stack>
            <Typography variant="h4" color="primary.main" sx={{ mt: 2 }}>{Number(plan.price_monthly).toFixed(0)} €/mes</Typography>
            <Typography color="text.secondary">Pago unico: {Number(plan.price_single).toFixed(0)} €</Typography>
            <Divider sx={{ my: 2 }} />
            <List dense sx={{ maxHeight: 330, overflow: 'auto' }}>
              {plan.services.map((item) => <ListItem key={item.id} disableGutters><ListItemText primary={item.name} secondary={item.notes} /></ListItem>)}
            </List>
          </CardContent></Card>)}
        </Box>
      </Box>
    </Stack>
  )
}
