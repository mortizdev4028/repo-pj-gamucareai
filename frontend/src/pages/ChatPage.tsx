import { useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, FormControl,
  InputLabel, Link, MenuItem, Select, Stack, TextField, ToggleButton,
  ToggleButtonGroup, Typography
} from '@mui/material'
import SendRoundedIcon from '@mui/icons-material/SendRounded'
import SmartToyRoundedIcon from '@mui/icons-material/SmartToyRounded'
import PublicRoundedIcon from '@mui/icons-material/PublicRounded'
import MedicalInformationRoundedIcon from '@mui/icons-material/MedicalInformationRounded'
import PetsRoundedIcon from '@mui/icons-material/PetsRounded'
import { Link as RouterLink, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { ChatResponse, PetListItem } from '../types'

interface Message { role: 'user' | 'assistant'; content: string; response?: ChatResponse }
type ChatScope = 'general' | 'clinical' | 'pet'

const defaultQuestion: Record<ChatScope, string> = {
  clinical: 'Que problemas recurrentes aparecen en perros braquicefalicos?',
  general: 'Que necesito para viajar con mi perro por la Union Europea?',
  pet: 'Que tiene pendiente mi mascota dentro de su plan de salud?'
}

export function ChatPage() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const requestedPetId = searchParams.get('pet_id') || ''
  const clinicalAccess = user?.role === 'clinic' || user?.role === 'staff'
  const initialScope: ChatScope = clinicalAccess ? 'clinical' : 'pet'
  const [scope, setScope] = useState<ChatScope>(initialScope)
  const [pets, setPets] = useState<PetListItem[]>([])
  const [selectedPetId, setSelectedPetId] = useState(requestedPetId)
  const [question, setQuestion] = useState(defaultQuestion[initialScope])
  const [messages, setMessages] = useState<Message[]>([])
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)
  const [loadingPets, setLoadingPets] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoadingPets(true)
    api.get<PetListItem[]>('/pets')
      .then((response) => {
        setPets(response.data)
        const allowedRequested = requestedPetId && response.data.some((pet) => pet.id === requestedPetId)
        if (allowedRequested) {
          setSelectedPetId(requestedPetId)
          setScope('pet')
          setQuestion(defaultQuestion.pet)
        } else {
          setSelectedPetId((current) => current || response.data[0]?.id || '')
        }
      })
      .catch(() => setError('No se pudieron cargar las mascotas disponibles.'))
      .finally(() => setLoadingPets(false))
  }, [requestedPetId])

  const selectedPet = useMemo(
    () => pets.find((pet) => pet.id === selectedPetId),
    [pets, selectedPetId]
  )

  const resetConversation = (nextScope: ChatScope, petId = selectedPetId) => {
    setScope(nextScope)
    setSelectedPetId(petId)
    setMessages([])
    setSessionId(undefined)
    setError('')
    setQuestion(defaultQuestion[nextScope])
  }

  const changeScope = (_: React.MouseEvent<HTMLElement>, value: ChatScope | null) => {
    if (!value || value === scope) return
    resetConversation(value)
  }

  const changePet = (petId: string) => {
    resetConversation('pet', petId)
  }

  const ask = async () => {
    if (!question.trim() || loading || (scope === 'pet' && !selectedPetId)) return
    const current = question.trim()
    setMessages((items) => [...items, { role: 'user', content: current }])
    setQuestion('')
    setError('')
    setLoading(true)
    try {
      const response = await api.post<ChatResponse>('/chat/ask', {
        question: current,
        session_id: sessionId,
        scope,
        pet_id: scope === 'pet' ? selectedPetId : undefined
      })
      setSessionId(response.data.session_id)
      setMessages((items) => [...items, { role: 'assistant', content: response.data.answer, response: response.data }])
    } catch {
      setError('No se pudo consultar VetIA. Comprueba Ollama, Qdrant y la ultima reindexacion.')
    } finally {
      setLoading(false)
    }
  }

  const description = scope === 'clinical'
    ? 'Busca coincidencias y patrones dentro de los historiales ficticios de la clinica.'
    : scope === 'pet'
      ? `Consulta la ficha, historial visible, plan y pagos de ${selectedPet?.name || 'una mascota'}.`
      : 'Respuestas generales basadas en documentacion cargada en Qdrant.'

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">VetIA · asistente veterinario</Typography>
        <Typography color="text.secondary">{description}</Typography>
      </Box>

      <Stack direction={{ xs: 'column', md: 'row' }} gap={2} alignItems={{ md: 'center' }}>
        <ToggleButtonGroup exclusive value={scope} onChange={changeScope} size="small">
          {clinicalAccess && <ToggleButton value="clinical"><MedicalInformationRoundedIcon sx={{ mr: 1 }} />Historiales clinicos</ToggleButton>}
          <ToggleButton value="pet"><PetsRoundedIcon sx={{ mr: 1 }} />Datos de la mascota</ToggleButton>
          <ToggleButton value="general"><PublicRoundedIcon sx={{ mr: 1 }} />Informacion general</ToggleButton>
        </ToggleButtonGroup>

        {scope === 'pet' && (
          <FormControl size="small" sx={{ minWidth: 240 }} disabled={loadingPets || pets.length === 0}>
            <InputLabel>Mascota</InputLabel>
            <Select value={selectedPetId} label="Mascota" onChange={(event) => changePet(event.target.value)}>
              {pets.map((pet) => <MenuItem key={pet.id} value={pet.id}>{pet.name} · {pet.breed}</MenuItem>)}
            </Select>
          </FormControl>
        )}
      </Stack>

      <Alert severity={scope === 'clinical' ? 'warning' : 'info'}>
        {scope === 'clinical'
          ? 'El resultado se limita a la muestra recuperada y no representa prevalencia real. No sustituye el criterio veterinario.'
          : scope === 'pet'
            ? 'VetIA solo utiliza los datos autorizados de la mascota seleccionada. No genera diagnosticos nuevos ni prescribe tratamientos.'
            : 'VetIA no diagnostica ni sustituye la consulta con un veterinario.'}
      </Alert>

      {scope === 'pet' && pets.length === 0 && !loadingPets && (
        <Alert severity="warning">No hay mascotas disponibles para este usuario.</Alert>
      )}

      <Card><CardContent sx={{ minHeight: 440, display: 'flex', flexDirection: 'column' }}>
        <Stack spacing={2} sx={{ flex: 1, mb: 3 }}>
          {messages.length === 0 && (
            <Box sx={{ textAlign: 'center', my: 'auto', py: 8 }}>
              <SmartToyRoundedIcon color="primary" sx={{ fontSize: 70 }} />
              <Typography variant="h6">
                {scope === 'clinical'
                  ? 'Pregunta por razas, sintomas, diagnosticos o problemas repetidos.'
                  : scope === 'pet'
                    ? 'Pregunta por pagos, servicios pendientes, vacunas o antecedentes de la mascota seleccionada.'
                    : 'Pregunta sobre vacunas, viajes, tramites o prevencion.'}
              </Typography>
            </Box>
          )}

          {messages.map((message, index) => (
            <Box key={index} sx={{ alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '88%' }}>
              <Box sx={{
                p: 2, borderRadius: 4,
                bgcolor: message.role === 'user' ? 'primary.main' : '#f1eef8',
                color: message.role === 'user' ? 'white' : 'text.primary',
                whiteSpace: 'pre-wrap'
              }}>
                {message.content}
              </Box>
              {message.response && (
                <Stack direction="row" gap={1} flexWrap="wrap" sx={{ mt: 1 }}>
                  {message.response.sources.map((source, sourceIndex) => {
                    if (source.pet_id && source.content_type !== 'reference_document') {
                      const label = [source.pet_name, source.breed, source.event_date].filter(Boolean).join(' · ')
                      return (
                        <Chip
                          key={sourceIndex}
                          component={RouterLink}
                          to={`/pets/${source.pet_id}`}
                          clickable
                          size="small"
                          color="secondary"
                          label={`${source.citation_id || 'F'} · ${label || source.title} · ${(source.score * 100).toFixed(0)}%`}
                        />
                      )
                    }
                    return source.url ? (
                      <Link key={sourceIndex} href={source.url} target="_blank" rel="noreferrer">
                        <Chip clickable size="small" label={`${source.citation_id || 'F'} · ${source.source} · ${(source.score * 100).toFixed(0)}%`} />
                      </Link>
                    ) : (
                      <Chip key={sourceIndex} size="small" label={`${source.citation_id || 'F'} · ${source.source} · ${(source.score * 100).toFixed(0)}%`} />
                    )
                  })}
                  <Chip size="small" variant="outlined" label={`${message.response.response_time_ms} ms`} />
                  {message.response.diagnostics && (
                    <Chip
                      size="small"
                      color={message.response.diagnostics.confidence === 'high' ? 'success' : message.response.diagnostics.confidence === 'medium' ? 'warning' : 'error'}
                      label={`Confianza ${message.response.diagnostics.confidence}`}
                    />
                  )}
                  {message.response.diagnostics?.urgent && <Chip size="small" color="error" label="Posible urgencia" />}
                </Stack>
              )}
            </Box>
          ))}
          {loading && <CircularProgress size={28} />}
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>

        <Stack direction={{ xs: 'column', sm: 'row' }} gap={1.5}>
          <TextField
            fullWidth
            multiline
            maxRows={4}
            placeholder={scope === 'clinical' ? 'Ej.: Busca casos recurrentes de otitis...' : scope === 'pet' ? 'Ej.: Cuanto queda por pagar del plan?' : 'Escribe tu pregunta...'}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void ask()
              }
            }}
          />
          <Button
            variant="contained"
            endIcon={<SendRoundedIcon />}
            onClick={() => void ask()}
            disabled={loading || (scope === 'pet' && !selectedPetId)}
          >
            Enviar
          </Button>
        </Stack>
      </CardContent></Card>
    </Stack>
  )
}
