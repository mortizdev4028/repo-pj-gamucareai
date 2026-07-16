import { useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Checkbox, Chip, CircularProgress,
  FormControlLabel, LinearProgress, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography
} from '@mui/material'
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded'
import ScienceRoundedIcon from '@mui/icons-material/ScienceRounded'
import StorageRoundedIcon from '@mui/icons-material/StorageRounded'
import { api } from '../api/client'
import { apiErrorMessage } from '../api/errors'
import { useAuth } from '../auth/AuthContext'
import type { RagEvaluationRun, RagStatus } from '../types'

function percentage(value: unknown) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'
}

export function RagQualityPage() {
  const { user } = useAuth()
  const [status, setStatus] = useState<RagStatus | null>(null)
  const [run, setRun] = useState<RagEvaluationRun | null>(null)
  const [withGeneration, setWithGeneration] = useState(false)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [statusResponse, evaluationResponse] = await Promise.all([
        api.get<RagStatus>('/rag/status'),
        api.get<RagEvaluationRun | null>('/rag/evaluation/latest')
      ])
      setStatus(statusResponse.data)
      setRun(evaluationResponse.data)
    } catch {
      setError('No se pudo obtener el estado de VetIA. Comprueba la API y Qdrant.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const evaluate = async () => {
    setRunning(true)
    setError('')
    try {
      const response = await api.post<RagEvaluationRun>('/rag/evaluation/run', {
        with_generation: withGeneration
      })
      setRun(response.data)
    } catch (requestError: any) {
      setError(apiErrorMessage(requestError, 'No se pudo ejecutar la evaluacion.'))
    } finally {
      setRunning(false)
    }
  }

  if (loading) return <CircularProgress />

  const metrics = (run?.metrics || {}) as Record<string, any>
  const failedCases = run?.details?.filter((item) => !item.passed) || []

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Calidad de VetIA</Typography>
        <Typography color="text.secondary">
          Estado de la base de conocimiento y evaluacion repetible de recuperacion, rechazo y latencia.
        </Typography>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      <Stack direction={{ xs: 'column', lg: 'row' }} gap={2}>
        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Stack direction="row" alignItems="center" gap={1} mb={2}>
              <StorageRoundedIcon color="primary" />
              <Typography variant="h6">Coleccion vectorial</Typography>
            </Stack>
            <Stack direction="row" gap={1} flexWrap="wrap">
              <Chip color={status?.collection_available ? 'success' : 'error'} label={status?.collection_available ? 'Qdrant disponible' : 'Qdrant no disponible'} />
              <Chip label={`${status?.points_count || 0} vectores`} />
              <Chip label={`${status?.documents_completed || 0}/${status?.documents_total || 0} documentos`} />
              <Chip label={`${status?.external_files_available || 0}/${status?.source_manifest_total || 0} fuentes externas`} />
              <Chip label={status?.collection || 'sin coleccion'} variant="outlined" />
            </Stack>
            <Typography variant="body2" color="text.secondary" mt={2}>
              Ultima ingesta: {status?.latest_ingestion_at ? new Date(status.latest_ingestion_at).toLocaleString() : 'sin datos'}
            </Typography>
            {(status?.external_download_failures || 0) > 0 && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                La ultima descarga de fuentes tuvo {status?.external_download_failures} errores. Revisa data/rag_external/download-report.json.
              </Alert>
            )}
          </CardContent>
        </Card>

        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Typography variant="h6" mb={2}>Cobertura documental</Typography>
            <Stack direction="row" gap={1} flexWrap="wrap">
              {Object.entries(status?.categories || {}).map(([name, count]) => (
                <Chip key={name} label={`${name}: ${count}`} size="small" />
              ))}
            </Stack>
            <Typography variant="body2" color="text.secondary" mt={2}>
              Fuentes por nivel de confianza: {Object.entries(status?.trust_levels || {}).map(([name, count]) => `${name} ${count}`).join(' · ') || 'sin datos'}
            </Typography>
          </CardContent>
        </Card>
      </Stack>

      <Card>
        <CardContent>
          <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" gap={2} alignItems={{ md: 'center' }}>
            <Box>
              <Stack direction="row" gap={1} alignItems="center">
                <ScienceRoundedIcon color="secondary" />
                <Typography variant="h6">Evaluacion de VetIA</Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary">
                El modo recuperacion mide busqueda y rechazo. El modo completo tambien genera respuestas y tarda mas.
              </Typography>
            </Box>
            <Stack direction={{ xs: 'column', sm: 'row' }} gap={1} alignItems={{ sm: 'center' }}>
              <FormControlLabel
                control={<Checkbox checked={withGeneration} onChange={(event) => setWithGeneration(event.target.checked)} />}
                label="Incluir generacion"
              />
              <Button variant="outlined" startIcon={<RefreshRoundedIcon />} onClick={() => void load()}>Actualizar</Button>
              {user?.role === 'technical' && (
                <Button variant="contained" startIcon={<ScienceRoundedIcon />} disabled={running} onClick={() => void evaluate()}>
                  {running ? 'Evaluando…' : 'Ejecutar evaluacion'}
                </Button>
              )}
            </Stack>
          </Stack>
          {running && <LinearProgress sx={{ mt: 2 }} />}

          {run ? (
            <>
              <Stack direction="row" gap={1} flexWrap="wrap" mt={3}>
                <Chip label={`Estado: ${run.status}`} color={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'error' : 'warning'} />
                <Chip label={`Modo: ${run.mode}`} />
                <Chip label={`Dataset: ${run.dataset_name}`} />
                <Chip label={`${run.cases_total} casos`} />
                {run.model_name && <Chip label={run.model_name} variant="outlined" />}
              </Stack>

              {run.error && <Alert severity="error" sx={{ mt: 2 }}>{run.error}</Alert>}

              {run.status === 'completed' && (
                <Stack spacing={2} mt={3}>
                  <Stack direction={{ xs: 'column', md: 'row' }} gap={2}>
                    <Metric title="Acierto de recuperacion" value={percentage(metrics.retrieval_hit_rate)} />
                    <Metric title="MRR" value={typeof metrics.mrr === 'number' ? metrics.mrr.toFixed(3) : '—'} />
                    <Metric title="Rechazo correcto" value={percentage(metrics.no_context_accuracy)} />
                    <Metric title="P95 de busqueda" value={typeof metrics.latency_p95_ms === 'number' ? `${metrics.latency_p95_ms} ms` : '—'} />
                    <Metric title="Casos superados" value={`${metrics.passed_cases ?? 0}/${metrics.cases_total ?? run.cases_total}`} />
                  </Stack>

                  {metrics.rejection_reasons && typeof metrics.rejection_reasons === 'object' && (
                    <Stack direction="row" gap={1} flexWrap="wrap">
                      {Object.entries(metrics.rejection_reasons as Record<string, number>).map(([reason, count]) => (
                        <Chip key={reason} size="small" variant="outlined" label={`Rechazo ${reason}: ${count}`} />
                      ))}
                    </Stack>
                  )}

                  {failedCases.length > 0 ? (
                    <Box>
                      <Typography variant="subtitle1" fontWeight={800} mb={1}>Casos que requieren revision</Typography>
                      <TableContainer>
                        <Table size="small">
                          <TableHead><TableRow><TableCell>ID</TableCell><TableCell>Consulta</TableCell><TableCell>Decision</TableCell><TableCell>Resultados</TableCell><TableCell>Top score</TableCell><TableCell>Motivo</TableCell></TableRow></TableHead>
                          <TableBody>
                            {failedCases.map((item) => (
                              <TableRow key={item.id}>
                                <TableCell>{item.id}</TableCell>
                                <TableCell>{item.question}</TableCell>
                                <TableCell>{item.retrieval_decision || '—'}</TableCell>
                                <TableCell>{item.retrieved}</TableCell>
                                <TableCell>{(item.top_score * 100).toFixed(1)}%</TableCell>
                                <TableCell>{item.domain_reason || 'No se encontro el resultado esperado.'}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    </Box>
                  ) : <Alert severity="success">Todos los casos del dataset han superado el criterio automatico.</Alert>}
                </Stack>
              )}
            </>
          ) : (
            <Alert severity="info" sx={{ mt: 3 }}>Todavia no se ha ejecutado una evaluacion.</Alert>
          )}
        </CardContent>
      </Card>

      <Alert severity="warning">
        Estas metricas no sustituyen la revision humana. La fidelidad clinica, utilidad y claridad de VetIA deben evaluarse tambien con una rubrica veterinaria.
      </Alert>
    </Stack>
  )
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <Card variant="outlined" sx={{ flex: 1, minWidth: 150 }}>
      <CardContent>
        <Typography variant="caption" color="text.secondary">{title}</Typography>
        <Typography variant="h5" fontWeight={850}>{value}</Typography>
      </CardContent>
    </Card>
  )
}
