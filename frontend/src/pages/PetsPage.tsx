import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Card, CardActionArea, CardContent, Chip, CircularProgress,
  Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, IconButton,
  InputAdornment, MenuItem, Stack, Switch, TextField, Tooltip, Typography
} from '@mui/material'
import PetsRoundedIcon from '@mui/icons-material/PetsRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded'
import RestoreRoundedIcon from '@mui/icons-material/RestoreRounded'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { apiErrorMessage } from '../api/errors'
import { useAuth } from '../auth/AuthContext'
import type { OwnerListItem, PetListItem } from '../types'

interface PetForm {
  owner_id: string
  name: string
  species: 'dog' | 'cat'
  breed: string
  birth_date: string
  sex: string
  weight_kg: string
  neutered: boolean
  microchip: string
  allergies: string
  chronic_conditions: string
}

const emptyForm: PetForm = {
  owner_id: '', name: '', species: 'dog', breed: '', birth_date: '', sex: 'female',
  weight_kg: '', neutered: false, microchip: '', allergies: '', chronic_conditions: ''
}

export function PetsPage() {
  const { user } = useAuth()
  const canEdit = user?.role === 'clinic'
  const isOwner = user?.role === 'owner'
  const [pets, setPets] = useState<PetListItem[]>([])
  const [owners, setOwners] = useState<OwnerListItem[]>([])
  const [search, setSearch] = useState('')
  const [includeInactive, setIncludeInactive] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<PetListItem | null>(null)
  const [form, setForm] = useState<PetForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const navigate = useNavigate()

  const params = useMemo(() => ({
    search: search.trim() || undefined,
    include_inactive: !isOwner && includeInactive
  }), [search, includeInactive, isOwner])

  const loadPets = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get<PetListItem[]>('/pets', { params })
      setPets(response.data)
    } catch {
      setError('No se pudo cargar el listado de mascotas.')
    } finally {
      setLoading(false)
    }
  }, [params])

  useEffect(() => { void loadPets() }, [loadPets])

  useEffect(() => {
    if (!isOwner) {
      api.get<OwnerListItem[]>('/owners').then((response) => setOwners(response.data)).catch(() => undefined)
    }
  }, [isOwner])

  const openCreate = () => {
    setEditing(null)
    setForm({ ...emptyForm, owner_id: owners[0]?.id || '' })
    setDialogOpen(true)
  }

  const openEdit = (pet: PetListItem) => {
    setEditing(pet)
    setForm({
      owner_id: pet.owner.id,
      name: pet.name,
      species: pet.species,
      breed: pet.breed,
      birth_date: pet.birth_date,
      sex: pet.sex,
      weight_kg: String(pet.weight_kg),
      neutered: pet.neutered,
      microchip: pet.microchip || '',
      allergies: '',
      chronic_conditions: ''
    })
    setDialogOpen(true)
  }

  const savePet = async () => {
    setSaving(true)
    setError('')
    const payload: Record<string, unknown> = {
      ...form,
      weight_kg: Number(form.weight_kg),
      microchip: form.microchip.trim() || null,
      allergies: form.allergies.trim() || null,
      chronic_conditions: form.chronic_conditions.trim() || null
    }
    // The list endpoint does not expose clinical notes. Avoid clearing them
    // accidentally when editing demographic data from this dialog.
    if (editing) {
      delete payload.allergies
      delete payload.chronic_conditions
    }
    try {
      if (editing) {
        await api.patch(`/pets/${editing.id}`, payload)
        setNotice('La ficha de la mascota se ha actualizado.')
      } else {
        await api.post('/pets', payload)
        setNotice('Mascota creada correctamente.')
      }
      setDialogOpen(false)
      await loadPets()
    } catch (caught: any) {
      setError(apiErrorMessage(caught, 'No se pudo guardar la mascota.'))
    } finally {
      setSaving(false)
    }
  }

  const changeStatus = async (pet: PetListItem) => {
    const action = pet.is_active ? 'dar de baja' : 'reactivar'
    if (!window.confirm(`¿Confirmas que quieres ${action} a ${pet.name}?`)) return
    try {
      if (pet.is_active) await api.delete(`/pets/${pet.id}`)
      else await api.post(`/pets/${pet.id}/activate`)
      setNotice(pet.is_active ? 'Mascota dada de baja.' : 'Mascota reactivada.')
      await loadPets()
    } catch (caught: any) {
      setError(apiErrorMessage(caught, 'No se pudo cambiar el estado de la mascota.'))
    }
  }

  const requiredMissing = !form.owner_id || !form.name.trim() || !form.breed.trim() || !form.birth_date || !form.sex.trim() || Number(form.weight_kg) <= 0

  return (
    <Stack spacing={3}>
      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={2}>
        <Box>
          <Typography variant="h4">{isOwner ? 'Mis mascotas' : 'Mascotas'}</Typography>
          <Typography color="text.secondary">{isOwner ? 'Consulta su plan de salud y sus proximas prestaciones.' : 'Pacientes registrados y estado de sus planes LifeCare.'}</Typography>
        </Box>
        {canEdit && <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={openCreate} disabled={owners.length === 0}>Nueva mascota</Button>}
      </Stack>

      {user?.role === 'staff' && <Alert severity="info">Tu perfil puede consultar todas las fichas, pero no crear ni modificar mascotas.</Alert>}
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {notice && <Alert severity="success" onClose={() => setNotice('')}>{notice}</Alert>}

      <Card><CardContent>
        <Stack direction={{ xs: 'column', md: 'row' }} gap={2} alignItems={{ md: 'center' }}>
          <TextField
            fullWidth
            label="Buscar mascota"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Nombre, raza, microchip o propietario"
            InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon /></InputAdornment> }}
          />
          {!isOwner && <FormControlLabel
            sx={{ minWidth: 190 }}
            control={<Switch checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />}
            label="Mostrar bajas"
          />}
        </Stack>
      </CardContent></Card>

      {loading ? <Box sx={{ display: 'grid', placeItems: 'center', minHeight: 300 }}><CircularProgress /></Box> :
        pets.length === 0 ? <Alert severity="info">No hay mascotas que coincidan con la busqueda.</Alert> :
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2,1fr)', xl: 'repeat(3,1fr)' } }}>
          {pets.map((pet) => (
            <Card key={pet.id} sx={{ position: 'relative', opacity: pet.is_active ? 1 : .65 }}>
              <CardActionArea onClick={() => navigate(`/pets/${pet.id}`)} sx={{ height: '100%' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                    <Box sx={{ width: 58, height: 58, borderRadius: 4, bgcolor: pet.species === 'dog' ? '#fef3c7' : '#ede9fe', display: 'grid', placeItems: 'center' }}><PetsRoundedIcon color="primary" /></Box>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography variant="h6" noWrap>{pet.name}</Typography>
                      <Typography color="text.secondary" noWrap>{pet.breed}</Typography>
                      {!isOwner && <Typography variant="caption" color="text.secondary">{pet.owner.first_name} {pet.owner.last_name}</Typography>}
                    </Box>
                  </Box>
                  <Stack direction="row" gap={1} flexWrap="wrap" sx={{ mt: 2 }}>
                    <Chip size="small" label={pet.species === 'dog' ? 'Perro' : 'Gato'} />
                    <Chip size="small" label={`${Number(pet.weight_kg).toFixed(1)} kg`} variant="outlined" />
                    <Chip size="small" label={pet.is_active ? pet.external_id : 'Baja'} color={pet.is_active ? 'default' : 'warning'} variant="outlined" />
                  </Stack>
                </CardContent>
              </CardActionArea>
              {canEdit && <Stack direction="row" sx={{ position: 'absolute', top: 8, right: 8, bgcolor: 'rgba(255,255,255,.9)', borderRadius: 3 }}>
                <Tooltip title="Editar"><IconButton size="small" onClick={(event) => { event.stopPropagation(); openEdit(pet) }}><EditRoundedIcon fontSize="small" /></IconButton></Tooltip>
                <Tooltip title={pet.is_active ? 'Dar de baja' : 'Reactivar'}>
                  <IconButton size="small" onClick={(event) => { event.stopPropagation(); void changeStatus(pet) }}>
                    {pet.is_active ? <VisibilityOffRoundedIcon fontSize="small" /> : <RestoreRoundedIcon fontSize="small" />}
                  </IconButton>
                </Tooltip>
              </Stack>}
            </Card>
          ))}
        </Box>}

      <Dialog open={dialogOpen} onClose={() => !saving && setDialogOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>{editing ? 'Editar mascota' : 'Nueva mascota'}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' }, pt: 1 }}>
            <TextField select label="Propietario" value={form.owner_id} onChange={(event) => setForm({ ...form, owner_id: event.target.value })} required>
              {owners.map((owner) => <MenuItem key={owner.id} value={owner.id}>{owner.first_name} {owner.last_name}</MenuItem>)}
            </TextField>
            <TextField label="Nombre" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
            <TextField select label="Especie" value={form.species} onChange={(event) => setForm({ ...form, species: event.target.value as 'dog' | 'cat' })}>
              <MenuItem value="dog">Perro</MenuItem><MenuItem value="cat">Gato</MenuItem>
            </TextField>
            <TextField label="Raza" value={form.breed} onChange={(event) => setForm({ ...form, breed: event.target.value })} required />
            <TextField type="date" label="Fecha de nacimiento" InputLabelProps={{ shrink: true }} value={form.birth_date} onChange={(event) => setForm({ ...form, birth_date: event.target.value })} required />
            <TextField select label="Sexo" value={form.sex} onChange={(event) => setForm({ ...form, sex: event.target.value })}>
              <MenuItem value="female">Hembra</MenuItem><MenuItem value="male">Macho</MenuItem>
            </TextField>
            <TextField type="number" label="Peso (kg)" inputProps={{ min: 0.1, step: 0.1 }} value={form.weight_kg} onChange={(event) => setForm({ ...form, weight_kg: event.target.value })} required />
            <TextField label="Microchip" value={form.microchip} onChange={(event) => setForm({ ...form, microchip: event.target.value })} />
            <FormControlLabel control={<Switch checked={form.neutered} onChange={(event) => setForm({ ...form, neutered: event.target.checked })} />} label="Esterilizada/o" />
            <Box />
            <TextField multiline minRows={2} label="Alergias" value={form.allergies} onChange={(event) => setForm({ ...form, allergies: event.target.value })} />
            <TextField multiline minRows={2} label="Antecedentes" value={form.chronic_conditions} onChange={(event) => setForm({ ...form, chronic_conditions: event.target.value })} />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} disabled={saving}>Cancelar</Button>
          <Button variant="contained" onClick={() => void savePet()} disabled={saving || requiredMissing}>{saving ? 'Guardando...' : 'Guardar'}</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  )
}
