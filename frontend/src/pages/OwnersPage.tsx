import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog,
  DialogActions, DialogContent, DialogTitle, FormControlLabel, IconButton,
  InputAdornment, Stack, Switch, TextField, Tooltip, Typography
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import PersonOffRoundedIcon from '@mui/icons-material/PersonOffRounded'
import PersonAddAltRoundedIcon from '@mui/icons-material/PersonAddAltRounded'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import PetsRoundedIcon from '@mui/icons-material/PetsRounded'
import { api } from '../api/client'
import { apiErrorMessage } from '../api/errors'
import { useAuth } from '../auth/AuthContext'
import type { OwnerCreateResponse, OwnerListItem } from '../types'

interface OwnerForm {
  first_name: string
  last_name: string
  phone: string
  email: string
  address: string
}

const emptyForm: OwnerForm = {
  first_name: '', last_name: '', phone: '', email: '', address: ''
}

export function OwnersPage() {
  const { user } = useAuth()
  const canEdit = user?.role === 'clinic'
  const [owners, setOwners] = useState<OwnerListItem[]>([])
  const [search, setSearch] = useState('')
  const [includeInactive, setIncludeInactive] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<OwnerListItem | null>(null)
  const [form, setForm] = useState<OwnerForm>(emptyForm)
  const [saving, setSaving] = useState(false)

  const params = useMemo(() => ({
    search: search.trim() || undefined,
    include_inactive: includeInactive
  }), [search, includeInactive])

  const loadOwners = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get<OwnerListItem[]>('/owners', { params })
      setOwners(response.data)
    } catch {
      setError('No se pudo cargar el listado de clientes.')
    } finally {
      setLoading(false)
    }
  }, [params])

  useEffect(() => { void loadOwners() }, [loadOwners])

  const openCreate = () => {
    setEditing(null)
    setForm(emptyForm)
    setDialogOpen(true)
  }

  const openEdit = (owner: OwnerListItem) => {
    setEditing(owner)
    setForm({
      first_name: owner.first_name,
      last_name: owner.last_name,
      phone: owner.phone,
      email: owner.email,
      address: owner.address
    })
    setDialogOpen(true)
  }

  const saveOwner = async () => {
    setSaving(true)
    setError('')
    try {
      if (editing) {
        await api.patch(`/owners/${editing.id}`, form)
        setNotice('Los datos del cliente se han actualizado.')
      } else {
        const response = await api.post<OwnerCreateResponse>('/owners', form)
        setNotice(`Cliente creado. Usuario: ${response.data.email} · Contrasena temporal: ${response.data.temporary_password}`)
      }
      setDialogOpen(false)
      await loadOwners()
    } catch (caught: any) {
      setError(apiErrorMessage(caught, 'No se pudo guardar el cliente.'))
    } finally {
      setSaving(false)
    }
  }

  const changeStatus = async (owner: OwnerListItem) => {
    const action = owner.is_active ? 'dar de baja' : 'reactivar'
    if (!window.confirm(`¿Confirmas que quieres ${action} a ${owner.first_name} ${owner.last_name}?`)) return
    setError('')
    try {
      if (owner.is_active) await api.delete(`/owners/${owner.id}`)
      else await api.post(`/owners/${owner.id}/activate`)
      setNotice(owner.is_active ? 'Cliente dado de baja. Sus mascotas tambien quedan inactivas.' : 'Cliente reactivado.')
      await loadOwners()
    } catch (caught: any) {
      setError(apiErrorMessage(caught, 'No se pudo cambiar el estado del cliente.'))
    }
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2}>
          <Box>
            <Typography variant="h4">Clientes</Typography>
            <Typography color="text.secondary">Propietarios, acceso al portal y mascotas asociadas.</Typography>
          </Box>
          {canEdit && <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={openCreate}>Nuevo cliente</Button>}
        </Stack>
      </Box>

      {user?.role === 'staff' && <Alert severity="info">Tu perfil es de solo lectura. Puedes consultar todos los datos, pero no modificarlos.</Alert>}
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {notice && <Alert severity="success" onClose={() => setNotice('')}>{notice}</Alert>}

      <Card><CardContent>
        <Stack direction={{ xs: 'column', md: 'row' }} gap={2} alignItems={{ md: 'center' }}>
          <TextField
            fullWidth
            label="Buscar cliente"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Nombre, correo, telefono o identificador"
            InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon /></InputAdornment> }}
          />
          <FormControlLabel
            sx={{ minWidth: 190 }}
            control={<Switch checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />}
            label="Mostrar bajas"
          />
        </Stack>
      </CardContent></Card>

      {loading ? (
        <Box sx={{ display: 'grid', placeItems: 'center', minHeight: 260 }}><CircularProgress /></Box>
      ) : owners.length === 0 ? (
        <Alert severity="info">No hay clientes que coincidan con la busqueda.</Alert>
      ) : (
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, 1fr)' } }}>
          {owners.map((owner) => (
            <Card key={owner.id} sx={{ opacity: owner.is_active ? 1 : .65 }}>
              <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={2}>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography variant="h6" noWrap>{owner.first_name} {owner.last_name}</Typography>
                    <Typography color="text.secondary" noWrap>{owner.email}</Typography>
                    <Typography variant="body2" color="text.secondary">{owner.phone} · {owner.external_id}</Typography>
                  </Box>
                  <Chip size="small" label={owner.is_active ? 'Activo' : 'Baja'} color={owner.is_active ? 'success' : 'default'} />
                </Stack>
                <Typography variant="body2" sx={{ mt: 2 }}>{owner.address}</Typography>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 2 }}>
                  <Chip icon={<PetsRoundedIcon />} label={`${owner.pet_count} mascota${owner.pet_count === 1 ? '' : 's'}`} variant="outlined" />
                  {canEdit && <Stack direction="row">
                    <Tooltip title="Editar"><IconButton onClick={() => openEdit(owner)}><EditRoundedIcon /></IconButton></Tooltip>
                    <Tooltip title={owner.is_active ? 'Dar de baja' : 'Reactivar'}>
                      <IconButton onClick={() => void changeStatus(owner)} color={owner.is_active ? 'default' : 'primary'}>
                        {owner.is_active ? <PersonOffRoundedIcon /> : <PersonAddAltRoundedIcon />}
                      </IconButton>
                    </Tooltip>
                  </Stack>}
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}

      <Dialog open={dialogOpen} onClose={() => !saving && setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editing ? 'Editar cliente' : 'Nuevo cliente'}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, pt: 1 }}>
            <TextField label="Nombre" value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} required />
            <TextField label="Apellidos" value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} required />
            <TextField label="Telefono" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} required />
            <TextField label="Correo" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required />
            <TextField label="Direccion" value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} required sx={{ gridColumn: { sm: '1 / -1' } }} />
          </Box>
          {!editing && <Alert severity="info" sx={{ mt: 2 }}>Se creara automaticamente un usuario propietario. La contrasena temporal se mostrara una sola vez.</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} disabled={saving}>Cancelar</Button>
          <Button variant="contained" onClick={() => void saveOwner()} disabled={saving || Object.values(form).some((value) => !value.trim())}>
            {saving ? 'Guardando...' : 'Guardar'}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  )
}
