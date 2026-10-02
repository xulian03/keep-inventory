import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
} from '@mui/material'
import { useAuth } from '../auth/AuthContext'
import { fetchCategories, STATE_COLORS } from '../api/shared'
import {
  fetchPredictions,
  type PredictionMethod,
  type PredictionTrend,
  type PredictionsResponse,
} from './api'

const PAGE_SIZE = 50

function formatQuantity(value: number): string {
  return value.toLocaleString('es-ES', { maximumFractionDigits: 2 })
}

function formatMethod(value: PredictionMethod): string {
  return { regresion: 'Regresión', media_movil: 'Media móvil' }[value]
}

function formatTrend(value: PredictionTrend): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export default function PrediccionesPanel() {
  const { token } = useAuth()

  // Sin categoría (todas) y página 1 (TablePagination la representa 0-indexada).
  const [category, setCategory] = useState('')
  const [page, setPage] = useState(0)
  const [categories, setCategories] = useState<string[]>([])

  const [result, setResult] = useState<{
    key: string
    data: PredictionsResponse | null
    error: string | null
  }>({ key: '', data: null, error: null })

  const queryKey = token
    ? JSON.stringify({ category, page, pageSize: PAGE_SIZE })
    : ''

  // La fábrica usa el closure del render actual; el efecto sólo depende de la
  // clave de la petición.
  const factoryRef = useRef<(() => Promise<PredictionsResponse>) | null>(null)
  useEffect(() => {
    factoryRef.current = token
      ? () =>
          fetchPredictions(token, {
            category: category || undefined,
            page: page + 1,
            page_size: PAGE_SIZE,
          })
      : null
  })

  useEffect(() => {
    if (!queryKey) return
    const factory = factoryRef.current
    if (!factory) return
    let active = true
    factory()
      .then((data) => {
        if (active) setResult({ key: queryKey, data, error: null })
      })
      .catch((err: unknown) => {
        if (active)
          setResult({
            key: queryKey,
            data: null,
            error:
              err instanceof Error ? err.message : 'Error al cargar las predicciones',
          })
      })
    return () => {
      active = false
    }
  }, [queryKey])

  useEffect(() => {
    if (!token) return
    let active = true
    fetchCategories(token)
      .then((response) => {
        if (active) setCategories(response.categories)
      })
      .catch(() => {
        // La tabla sigue usable aunque no carguen las categorías.
      })
    return () => {
      active = false
    }
  }, [token])

  const fresh = result.key === queryKey
  const data = fresh ? result.data : null
  const error = fresh ? result.error : null
  const loading = queryKey !== '' && !fresh

  const handleCategoryChange = (value: string) => {
    setCategory(value)
    setPage(0)
  }

  return (
    <Stack spacing={3}>
      <Card
        variant="outlined"
        sx={{ borderRadius: '14px', borderColor: '#E5E7EB', boxShadow: 'none' }}
      >
        <CardContent>
          <FormControl size="small" sx={{ minWidth: 220 }}>
            <InputLabel id="predicciones-category-label">Categoría</InputLabel>
            <Select
              labelId="predicciones-category-label"
              label="Categoría"
              value={category}
              onChange={(event) => handleCategoryChange(event.target.value)}
            >
              <MenuItem value="">Todas</MenuItem>
              {categories.map((item) => (
                <MenuItem key={item} value={item}>
                  {item}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </CardContent>
      </Card>

      {error ? (
        <Alert severity="error">{error}</Alert>
      ) : (
        <Card
          variant="outlined"
          sx={{ borderRadius: '14px', borderColor: '#E5E7EB', boxShadow: 'none' }}
        >
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Predicciones
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Demanda estimada y reposición sugerida
              {data ? ` (${data.total.toLocaleString('es-ES')} productos)` : ''}
            </Typography>

            {loading ? (
              <Box sx={{ py: 6, display: 'flex', justifyContent: 'center' }}>
                <CircularProgress size={32} />
              </Box>
            ) : (
              <>
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Producto</TableCell>
                        <TableCell>Categoría</TableCell>
                        <TableCell align="right">Stock</TableCell>
                        <TableCell align="right">Umbral</TableCell>
                        <TableCell>Estado</TableCell>
                        <TableCell>Método</TableCell>
                        <TableCell align="right">Demanda/día</TableCell>
                        <TableCell>Tendencia</TableCell>
                        <TableCell>Agotamiento</TableCell>
                        <TableCell align="right">Demanda 30d</TableCell>
                        <TableCell align="right">Sugerido</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(data?.items ?? []).length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={11} align="center">
                            <Typography variant="body2" color="text.secondary">
                              Sin resultados.
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ) : (
                        data?.items.map((item) => (
                          <TableRow key={item.product_id} hover>
                            <TableCell>{item.product_name}</TableCell>
                            <TableCell>{item.category}</TableCell>
                            <TableCell align="right">
                              {formatQuantity(item.stock)}
                            </TableCell>
                            <TableCell align="right">
                              {formatQuantity(item.min_threshold)}
                            </TableCell>
                            <TableCell>
                              <Chip
                                size="small"
                                label={item.state}
                                sx={{
                                  bgcolor: STATE_COLORS[item.state],
                                  color: '#FFFFFF',
                                  fontWeight: 600,
                                }}
                              />
                            </TableCell>
                            <TableCell>{formatMethod(item.method)}</TableCell>
                            <TableCell align="right">
                              {formatQuantity(item.daily_demand)}
                            </TableCell>
                            <TableCell>{formatTrend(item.trend)}</TableCell>
                            <TableCell>{item.stockout_date ?? '—'}</TableCell>
                            <TableCell align="right">
                              {formatQuantity(item.demand_30d)}
                            </TableCell>
                            <TableCell align="right">
                              {formatQuantity(item.suggested_reorder)}
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>

                <TablePagination
                  component="div"
                  count={data?.total ?? 0}
                  page={page}
                  onPageChange={(_event, newPage) => setPage(newPage)}
                  rowsPerPage={PAGE_SIZE}
                  rowsPerPageOptions={[PAGE_SIZE]}
                  labelRowsPerPage="Filas por página"
                  labelDisplayedRows={({ from, to, count }) =>
                    `${from}–${to} de ${count.toLocaleString('es-ES')}`
                  }
                />
              </>
            )}
          </CardContent>
        </Card>
      )}
    </Stack>
  )
}
