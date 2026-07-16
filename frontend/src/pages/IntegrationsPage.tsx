import { ChangeEvent, useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog,
  DialogActions, DialogContent, DialogTitle, Divider, Grid, LinearProgress,
  Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, Tooltip, Typography
} from '@mui/material'
import CloudUploadRoundedIcon from '@mui/icons-material/CloudUploadRounded'
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded'
import FactCheckRoundedIcon from '@mui/icons-material/FactCheckRounded'
import SyncRoundedIcon from '@mui/icons-material/SyncRounded'
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type {
  ImportBatchDetail, ImportBatchSummary, TemporaryCredential,
  WakymaImportResult, WakymaIntegrationStatus
} from '../types'

const statusLabels: Record<string, string> = {
  validating: 'Validando', processing: 'Procesando', validated: 'Validado',
  validated_with_errors: 'Validado con errores', validation_failed: 'Validacion fallida',
  completed: 'Completado', completed_with_errors: 'Completado con errores',
  failed: 'Fallido', empty: 'Sin registros'
}

function statusColor(status: string): 'success' | 'warning' | 'error' | 'default' | 'info' {
  if (status === 'completed' || status === 'validated') return 'success'
  if (status.includes('with_errors')) return 'warning'
  if (status === 'processing' || status === 'validating') return 'info'
  if (status === 'failed' || status === 'validation_failed') return 'error'
  return 'default'
}

function formatDate(value?: string) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))
}

export function IntegrationsPage() {
  const { user } = useAuth()
  const [statusInfo, setStatusInfo] = useState<WakymaIntegrationStatus | null>(null)
  const [batches, setBatches] = useState<ImportBatchSummary[]>([])
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [working, setWorking] = useState(false)
  const [message, setMessage] = useState<{ severity: 'success' | 'error' | 'warning'; text: string } | null>(null)
  const [result, setResult] = useState<WakymaImportResult | null>(null)
  const [detail, setDetail] = useState<ImportBatchDetail | null>(null)
  const [credentials, setCredentials] = useState<TemporaryCredential[]>([])

  const canWrite = user?.role === 'technical'

  const load = useCallback(async () => {
    const [statusResponse, historyResponse] = await Promise.all([
      api.get<WakymaIntegrationStatus>('/integrations/wakyma/status'),
      api.get<ImportBatchSummary[]>('/integrations/wakyma/imports')
    ])
    setStatusInfo(statusResponse.data)
    setBatches(historyResponse.data)
  }, [])

  useEffect(() => {
    load().catch(() => setMessage({ severity: 'error', text: 'No se pudo cargar el estado de la integracion.' }))
  }, [load])

  const fileHint = useMemo(() => {
    if (!selectedFile) return 'Selecciona un JSON o CSV de hasta 5 MB.'
    return `${selectedFile.name} · ${(selectedFile.size / 1024).toFixed(1)} KB`
  }, [selectedFile])

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] || null
    setSelectedFile(file)
    setMessage(null)
    setResult(null)
  }

  async function submit(dryRun: boolean) {
    if (!selectedFile) {
      setMessage({ severity: 'warning', text: 'Selecciona primero un fichero.' })
      return
    }
    setWorking(true)
    setMessage(null)
    try {
      const form = new FormData()
      form.append('file', selectedFile)
      const response = await api.post<WakymaImportResult>(
        `/integrations/wakyma/imports?dry_run=${dryRun}`,
        form
      )
      setResult(response.data)
      setCredentials(response.data.temporary_credentials)
      const errors = response.data.batch.records_failed
      setMessage({
        severity: errors ? 'warning' : 'success',
        text: dryRun
          ? `Validacion finalizada: ${response.data.batch.records_processed} registros correctos y ${errors} errores.`
          : `Importacion finalizada: ${response.data.batch.records_created} creados, ${response.data.batch.records_updated} actualizados y ${errors} errores.`
      })
      await load()
    } catch (error: any) {
      const detail = error.response?.data?.detail
      setMessage({ severity: 'error', text: typeof detail === 'string' ? detail : 'La operacion no se pudo completar.' })
    } finally {
      setWorking(false)
    }
  }

  async function openDetail(id: string) {
    try {
      const response = await api.get<ImportBatchDetail>(`/integrations/wakyma/imports/${id}`)
      setDetail(response.data)
    } catch {
      setMessage({ severity: 'error', text: 'No se pudo abrir el detalle de la importacion.' })
    }
  }

  async function downloadTemplate(format: 'json' | 'csv') {
    const response = await api.get(`/integrations/wakyma/templates/${format}`, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `wakyma_import_template.${format}`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  function exportCredentials() {
    if (!credentials.length) return
    const rows = ['external_id;email;temporary_password', ...credentials.map((item) =>
      `${item.external_id};${item.email};${item.temporary_password}`
    )]
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'credenciales_temporales_wakyma.csv'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" fontWeight={850}>Integracion Wakyma</Typography>
        <Typography color="text.secondary" sx={{ mt: 0.5 }}>
          Conector simulado para validar e importar propietarios, mascotas e historiales desde JSON o CSV.
        </Typography>
      </Box>

      <Alert severity="info">
        Esta version no se conecta a una API comercial real. Los ficheros son ficticios y el adaptador esta preparado para sustituirse por un cliente real en una fase posterior.
      </Alert>

      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}><CardContent>
            <Typography variant="overline" color="text.secondary">Conector</Typography>
            <Typography variant="h6" fontWeight={800}>{statusInfo?.connector || 'wakyma_mock'}</Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
              {statusInfo?.supported_formats.map((format) => <Chip key={format} label={format.toUpperCase()} />)}
              <Chip label="Sin API real" color="warning" variant="outlined" />
            </Stack>
          </CardContent></Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}><CardContent>
            <Typography variant="overline" color="text.secondary">Entidades</Typography>
            <Typography variant="h6" fontWeight={800}>3 tipos soportados</Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>Clientes, mascotas y eventos clinicos.</Typography>
          </CardContent></Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}><CardContent>
            <Typography variant="overline" color="text.secondary">Trazabilidad</Typography>
            <Typography variant="h6" fontWeight={800}>Auditoria por registro</Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>Checksum, usuario, fecha, accion y errores de cada fila.</Typography>
          </CardContent></Card>
        </Grid>
      </Grid>

      <Paper sx={{ p: { xs: 2, md: 3 }, borderRadius: 4 }}>
        <Stack spacing={2}>
          <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" gap={2}>
            <Box>
              <Typography variant="h6" fontWeight={800}>Nueva importacion</Typography>
              <Typography variant="body2" color="text.secondary">Valida primero el fichero. La validacion no modifica datos.</Typography>
            </Box>
            <Stack direction="row" spacing={1}>
              <Button startIcon={<DownloadRoundedIcon />} onClick={() => downloadTemplate('json')}>Plantilla JSON</Button>
              <Button startIcon={<DownloadRoundedIcon />} onClick={() => downloadTemplate('csv')}>Plantilla CSV</Button>
            </Stack>
          </Stack>
          <Divider />
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ md: 'center' }}>
            <Button component="label" variant="outlined" startIcon={<CloudUploadRoundedIcon />}>
              Seleccionar fichero
              <input hidden type="file" accept=".json,.csv,application/json,text/csv" onChange={chooseFile} />
            </Button>
            <Typography variant="body2" color="text.secondary" sx={{ flexGrow: 1 }}>{fileHint}</Typography>
            <Button
              variant="contained" color="secondary" startIcon={<FactCheckRoundedIcon />}
              disabled={!selectedFile || working} onClick={() => submit(true)}
            >Validar</Button>
            <Tooltip title={canWrite ? 'Importa los registros validos' : 'Solo el perfil tecnico puede ejecutar importaciones'}>
              <span>
                <Button
                  variant="contained" startIcon={<SyncRoundedIcon />}
                  disabled={!selectedFile || working || !canWrite} onClick={() => submit(false)}
                >Importar</Button>
              </span>
            </Tooltip>
          </Stack>
          {working && <LinearProgress />}
          {message && <Alert severity={message.severity}>{message.text}</Alert>}
          {result && (
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip label={`Total ${result.batch.records_total}`} />
              <Chip label={`Creados ${result.batch.records_created}`} color="success" variant="outlined" />
              <Chip label={`Actualizados ${result.batch.records_updated}`} color="info" variant="outlined" />
              <Chip label={`Errores ${result.batch.records_failed}`} color={result.batch.records_failed ? 'error' : 'default'} variant="outlined" />
              <Button size="small" startIcon={<VisibilityRoundedIcon />} onClick={() => setDetail(result.batch)}>Ver detalle</Button>
            </Stack>
          )}
          {credentials.length > 0 && (
            <Alert severity="warning" action={<Button color="inherit" size="small" onClick={exportCredentials}>Descargar CSV</Button>}>
              Se han creado {credentials.length} cuentas de propietario. Las contrasenas temporales solo se muestran en esta respuesta y no quedan almacenadas en texto plano.
            </Alert>
          )}
        </Stack>
      </Paper>

      <Paper sx={{ borderRadius: 4, overflow: 'hidden' }}>
        <Box sx={{ p: 2.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" fontWeight={800}>Historial de importaciones</Typography>
          <Button onClick={load} startIcon={working ? <CircularProgress size={16} /> : <SyncRoundedIcon />}>Actualizar</Button>
        </Box>
        <TableContainer>
          <Table size="small">
            <TableHead><TableRow>
              <TableCell>Fecha</TableCell><TableCell>Fichero</TableCell><TableCell>Modo</TableCell>
              <TableCell>Estado</TableCell><TableCell align="right">Procesados</TableCell>
              <TableCell align="right">Errores</TableCell><TableCell />
            </TableRow></TableHead>
            <TableBody>
              {batches.map((batch) => (
                <TableRow key={batch.id} hover>
                  <TableCell>{formatDate(batch.started_at)}</TableCell>
                  <TableCell><Typography variant="body2" fontWeight={700}>{batch.filename}</Typography><Typography variant="caption" color="text.secondary">{batch.file_format.toUpperCase()} · esquema {batch.schema_version}</Typography></TableCell>
                  <TableCell>{batch.dry_run ? 'Validacion' : 'Importacion'}</TableCell>
                  <TableCell><Chip size="small" color={statusColor(batch.status)} label={statusLabels[batch.status] || batch.status} /></TableCell>
                  <TableCell align="right">{batch.records_processed}/{batch.records_total}</TableCell>
                  <TableCell align="right">{batch.records_failed}</TableCell>
                  <TableCell align="right"><Button size="small" onClick={() => openDetail(batch.id)}>Detalle</Button></TableCell>
                </TableRow>
              ))}
              {!batches.length && <TableRow><TableCell colSpan={7} align="center">No hay importaciones registradas.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Dialog open={Boolean(detail)} onClose={() => setDetail(null)} maxWidth="lg" fullWidth>
        <DialogTitle>Detalle de importacion</DialogTitle>
        <DialogContent dividers>
          {detail && <Stack spacing={2}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip label={statusLabels[detail.status] || detail.status} color={statusColor(detail.status)} />
              <Chip label={`${detail.records_created} creados`} variant="outlined" />
              <Chip label={`${detail.records_updated} actualizados`} variant="outlined" />
              <Chip label={`${detail.records_failed} errores`} variant="outlined" color={detail.records_failed ? 'error' : 'default'} />
            </Stack>
            <Typography variant="body2"><strong>Fichero:</strong> {detail.filename}</Typography>
            <Typography variant="body2" sx={{ wordBreak: 'break-all' }}><strong>SHA-256:</strong> {detail.checksum}</Typography>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead><TableRow><TableCell>Fila</TableCell><TableCell>Entidad</TableCell><TableCell>ID externo</TableCell><TableCell>Accion</TableCell><TableCell>Resultado</TableCell><TableCell>Detalle</TableCell></TableRow></TableHead>
                <TableBody>{detail.items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.row_number}</TableCell><TableCell>{item.entity_type}</TableCell>
                    <TableCell>{item.external_id || '-'}</TableCell><TableCell>{item.action}</TableCell>
                    <TableCell><Chip size="small" label={item.status} color={item.status === 'error' ? 'error' : 'success'} variant="outlined" /></TableCell>
                    <TableCell>{item.message}</TableCell>
                  </TableRow>
                ))}</TableBody>
              </Table>
            </TableContainer>
          </Stack>}
        </DialogContent>
        <DialogActions><Button onClick={() => setDetail(null)}>Cerrar</Button></DialogActions>
      </Dialog>
    </Stack>
  )
}
