import { useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Checkbox, Chip, CircularProgress,
  FormControlLabel, LinearProgress, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography
} from '@mui/material'
import AssessmentRoundedIcon from '@mui/icons-material/AssessmentRounded'
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded'
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded'
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded'
import VerifiedRoundedIcon from '@mui/icons-material/VerifiedRounded'
import { api } from '../api/client'
import { apiErrorMessage } from '../api/errors'
import { useAuth } from '../auth/AuthContext'
import type { EvaluationCase, QualityStatus, SystemEvaluationRun } from '../types'

function percent(value: unknown) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'
}

function numberValue(value: unknown, suffix = '') {
  return typeof value === 'number' ? `${value.toFixed(2)}${suffix}` : '—'
}

export function QualityPage() {
  const { user } = useAuth()
  const [status, setStatus] = useState<QualityStatus | null>(null)
  const [run, setRun] = useState<SystemEvaluationRun | null>(null)
  const [includeTests, setIncludeTests] = useState(true)
  const [includeVetia, setIncludeVetia] = useState(true)
  const [includePerformance, setIncludePerformance] = useState(true)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [statusResponse, latestResponse] = await Promise.all([
        api.get<QualityStatus>('/quality/status'),
        api.get<SystemEvaluationRun | null>('/quality/evaluation/latest')
      ])
      setStatus(statusResponse.data)
      setRun(latestResponse.data)
    } catch {
      setError('No se pudo cargar el estado de validacion del MVP.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const evaluate = async () => {
    setRunning(true)
    setError('')
    try {
      const response = await api.post<SystemEvaluationRun>('/quality/evaluation/run', {
        include_tests: includeTests,
        include_vetia: includeVetia,
        include_performance: includePerformance
      })
      setRun(response.data)
      await load()
    } catch (requestError: any) {
      setError(apiErrorMessage(requestError, 'No se pudo ejecutar la evaluacion formal.'))
    } finally {
      setRunning(false)
    }
  }

  const download = async () => {
    if (!run) return
    const response = await api.get(`/quality/evaluation/${run.id}/report`, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `gamucare-evaluation-${run.app_version}.md`
    link.click()
    URL.revokeObjectURL(url)
  }

  const failures = useMemo(() => {
    if (!run?.details) return [] as EvaluationCase[]
    return [
      ...(run.details.acceptance?.cases || []),
      ...(run.details.alerts?.cases || []),
      ...(run.details.security?.cases || [])
    ].filter((item) => !item.passed)
  }, [run])

  if (loading) return <CircularProgress />
  const metrics = run?.metrics || {}
  const tests = run?.details?.tests || {}
  const performance = run?.details?.performance || {}

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Validacion del MVP</Typography>
        <Typography color="text.secondary">
          Evidencias repetibles sobre requisitos funcionales, seguridad, avisos preventivos, VetIA y rendimiento.
        </Typography>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      <Stack direction={{ xs: 'column', md: 'row' }} gap={2}>
        <Card sx={{ flex: 1 }}><CardContent>
          <Typography variant="caption" color="text.secondary">Version evaluada</Typography>
          <Typography variant="h4" fontWeight={850}>v{status?.app_version || '—'}</Typography>
          <Typography variant="body2" color="text.secondary">{status?.automated_criteria || 0} criterios de aceptacion automatizados</Typography>
        </CardContent></Card>
        <Card sx={{ flex: 1 }}><CardContent>
          <Typography variant="caption" color="text.secondary">Resultado global</Typography>
          <Typography variant="h4" fontWeight={850}>{typeof metrics.overall_score === 'number' ? `${metrics.overall_score}/100` : 'Sin evaluar'}</Typography>
          {typeof metrics.overall_passed === 'boolean' && (
            <Chip sx={{ mt: 1 }} color={metrics.overall_passed ? 'success' : 'warning'} label={metrics.overall_passed ? 'APTO' : 'Requiere revision'} />
          )}
        </CardContent></Card>
        <Card sx={{ flex: 1 }}><CardContent>
          <Typography variant="caption" color="text.secondary">Ultima ejecucion</Typography>
          <Typography variant="h6" fontWeight={800}>{run ? new Date(run.started_at).toLocaleString() : 'Todavia no ejecutada'}</Typography>
          {run && <Chip sx={{ mt: 1 }} label={run.status} color={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'error' : 'warning'} />}
        </CardContent></Card>
      </Stack>

      <Card>
        <CardContent>
          <Stack direction={{ xs: 'column', lg: 'row' }} justifyContent="space-between" gap={2} alignItems={{ lg: 'center' }}>
            <Box>
              <Stack direction="row" gap={1} alignItems="center">
                <AssessmentRoundedIcon color="primary" />
                <Typography variant="h6">Suite formal v0.11</Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary">
                Las pruebas de codigo y VetIA aumentan el tiempo de ejecucion. El informe queda guardado en PostgreSQL.
              </Typography>
            </Box>
            <Stack direction={{ xs: 'column', md: 'row' }} gap={1} alignItems={{ md: 'center' }} flexWrap="wrap">
              <FormControlLabel control={<Checkbox checked={includeTests} onChange={(e) => setIncludeTests(e.target.checked)} />} label="Pruebas" />
              <FormControlLabel control={<Checkbox checked={includeVetia} onChange={(e) => setIncludeVetia(e.target.checked)} />} label="VetIA" />
              <FormControlLabel control={<Checkbox checked={includePerformance} onChange={(e) => setIncludePerformance(e.target.checked)} />} label="Rendimiento" />
              <Button variant="outlined" startIcon={<RefreshRoundedIcon />} onClick={() => void load()}>Actualizar</Button>
              {run?.status === 'completed' && <Button variant="outlined" startIcon={<DownloadRoundedIcon />} onClick={() => void download()}>Informe</Button>}
              {user?.role === 'technical' && (
                <Button variant="contained" startIcon={<PlayArrowRoundedIcon />} disabled={running} onClick={() => void evaluate()}>
                  {running ? 'Evaluando…' : 'Ejecutar'}
                </Button>
              )}
            </Stack>
          </Stack>
          {running && <LinearProgress sx={{ mt: 2 }} />}
        </CardContent>
      </Card>

      {run?.status === 'completed' && (
        <>
          <Stack direction={{ xs: 'column', sm: 'row' }} gap={2} flexWrap="wrap">
            <Metric title="Aceptacion" value={percent(metrics.acceptance_pass_rate)} />
            <Metric title="Pruebas" value={`${run.tests_passed}/${run.tests_total}`} />
            <Metric title="Cobertura" value={run.coverage_percent != null ? `${Number(run.coverage_percent).toFixed(1)}%` : '—'} />
            <Metric title="Avisos · exactitud" value={percent(metrics.alert_accuracy)} />
            <Metric title="Seguridad" value={percent(metrics.security_pass_rate)} />
            <Metric title="VetIA · recuperacion" value={percent(metrics.vetia_retrieval_hit_rate)} />
            <Metric title="API · P95" value={numberValue(metrics.api_latency_p95_ms, ' ms')} />
          </Stack>

          <Stack direction={{ xs: 'column', lg: 'row' }} gap={2}>
            <Card sx={{ flex: 1 }}><CardContent>
              <Typography variant="h6">Detalle tecnico</Typography>
              <Stack direction="row" gap={1} flexWrap="wrap" mt={2}>
                <Chip label={`Pytest: ${tests.status || 'n/d'}`} color={tests.status === 'passed' ? 'success' : 'default'} />
                <Chip label={`Fallos: ${tests.failed ?? 0}`} color={tests.failed ? 'error' : 'success'} />
                <Chip label={`P50 API: ${performance.latency_p50_ms ?? 'n/d'} ms`} />
                <Chip label={`Solicitudes: ${performance.requests ?? 0}`} />
                <Chip label={`Errores API: ${performance.failures ?? 0}`} color={performance.failures ? 'error' : 'success'} />
              </Stack>
            </CardContent></Card>
            <Card sx={{ flex: 1 }}><CardContent>
              <Stack direction="row" gap={1} alignItems="center">
                <VerifiedRoundedIcon color={failures.length ? 'warning' : 'success'} />
                <Typography variant="h6">Criterios que requieren revision</Typography>
              </Stack>
              <Typography variant="h3" fontWeight={850} mt={1}>{failures.length}</Typography>
            </CardContent></Card>
          </Stack>

          {failures.length > 0 ? (
            <Card><CardContent>
              <Typography variant="h6" mb={2}>Incidencias detectadas</Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead><TableRow><TableCell>ID</TableCell><TableCell>Area</TableCell><TableCell>Criterio</TableCell><TableCell>Evidencia</TableCell></TableRow></TableHead>
                  <TableBody>
                    {failures.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>{item.id}</TableCell>
                        <TableCell>{item.area || 'avisos'}</TableCell>
                        <TableCell>{item.description}</TableCell>
                        <TableCell>{typeof item.evidence === 'string' ? item.evidence : JSON.stringify(item.evidence || {})}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent></Card>
          ) : <Alert severity="success">Todos los criterios automaticos ejecutados han sido superados.</Alert>}
        </>
      )}

      {run?.status === 'failed' && <Alert severity="error">{run.error || 'La evaluacion ha fallado.'}</Alert>}
      {!run && <Alert severity="info">Ejecuta la primera evaluacion para generar evidencias del MVP.</Alert>}

      <Alert severity="warning">
        La validacion automatica no sustituye la revision veterinaria humana de la utilidad, fidelidad y seguridad clinica de las respuestas.
      </Alert>
    </Stack>
  )
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <Card variant="outlined" sx={{ flex: 1, minWidth: 155 }}>
      <CardContent>
        <Typography variant="caption" color="text.secondary">{title}</Typography>
        <Typography variant="h5" fontWeight={850}>{value}</Typography>
      </CardContent>
    </Card>
  )
}
