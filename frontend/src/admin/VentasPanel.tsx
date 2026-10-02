import { Fragment, useEffect, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Card,
  CardContent,
  CircularProgress,
  Collapse,
  FormControl,
  IconButton,
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
  TextField,
  Typography,
} from '@mui/material'
import { useAuth } from '../auth/AuthContext'
import { fetchCategories, formatMoney } from '../api/shared'
import { fetchSales, type SalesResponse } from './api'

const PAGE_SIZE = 50

function formatShortDate(value: string): string {
  return value.slice(0, 10)
}

function formatQuantity(value: number): string {
  return value.toLocaleString('es-ES', { maximumFractionDigits: 2 })
}

function totalUnits(items: { quantity: number }[]): number {
  return items.reduce((sum, item) => sum + item.quantity, 0)
}

export default function VentasPanel() {
  const { token } = useAuth()

  // Sin filtros y página 1 (TablePagination la representa 0-indexada).
  const [category, setCategory] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(0)
  const [categories, setCategories] = useState<string[]>([])
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const dateError = dateFrom !== '' && dateTo !== '' && dateFrom > dateTo

  const [result, setResult] = useState<{
    key: string
    data: SalesResponse | null
    error: string | null
  }>({ key: '', data: null, error: null })

  const queryKey =
    token && !dateError
      ? JSON.stringify({ category, dateFrom, dateTo, page, pageSize: PAGE_SIZE })
      : ''

  // La fábrica usa el closure del render actual; el efecto sólo depende de la
  // clave de la petición.
  const factoryRef = useRef<(() => Promise<SalesResponse>) | null>(null)
  useEffect(() => {
    factoryRef.current =
      token && !dateError
        ? () =>
            fetchSales(token, {
              category: category || undefined,
              date_from: dateFrom || undefined,
              date_to: dateTo || undefined,
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
            error: err instanceof Error ? err.message : 'Error al cargar las ventas',
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

  const handleDateFromChange = (value: string) => {
    setDateFrom(value)
    setPage(0)
  }

  const handleDateToChange = (value: string) => {
    setDateTo(value)
    setPage(0)
  }

  const toggleRow = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <Stack spacing={3}>
      <Card
        variant="outlined"
        sx={{ borderRadius: '14px', borderColor: '#E5E7EB', boxShadow: 'none' }}
      >
        <CardContent>
          <Stack
            direction={{ xs: 'column', md: 'row' }}
            spacing={2}
            useFlexGap
            sx={{ alignItems: { md: 'center' }, flexWrap: 'wrap' }}
          >
            <FormControl size="small" sx={{ minWidth: 220 }}>
              <InputLabel id="ventas-category-label">Categoría</InputLabel>
              <Select
                labelId="ventas-category-label"
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

            <TextField
              label="Desde"
              type="date"
              size="small"
              value={dateFrom}
              onChange={(event) => handleDateFromChange(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />

            <TextField
              label="Hasta"
              type="date"
              size="small"
              value={dateTo}
              onChange={(event) => handleDateToChange(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Stack>
        </CardContent>
      </Card>

      {dateError ? (
        <Alert severity="error">
          La fecha &quot;desde&quot; no puede ser posterior a la fecha &quot;hasta&quot;.
        </Alert>
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : (
        <Card
          variant="outlined"
          sx={{ borderRadius: '14px', borderColor: '#E5E7EB', boxShadow: 'none' }}
        >
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Ventas
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Historial de ventas registradas
              {data ? ` (${data.total.toLocaleString('es-ES')} ventas)` : ''}
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
                        <TableCell padding="checkbox" />
                        <TableCell>ID</TableCell>
                        <TableCell>Fecha</TableCell>
                        <TableCell>Vendedor</TableCell>
                        <TableCell align="right">Total</TableCell>
                        <TableCell align="right">Unidades</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(data?.items ?? []).length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={6} align="center">
                            <Typography variant="body2" color="text.secondary">
                              Sin resultados.
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ) : (
                        data?.items.map((sale) => {
                          const isOpen = expanded.has(sale.id)
                          return (
                            <Fragment key={sale.id}>
                              <TableRow hover>
                                <TableCell padding="checkbox">
                                  <IconButton
                                    size="small"
                                    aria-label={
                                      isOpen ? 'Contraer venta' : 'Expandir venta'
                                    }
                                    onClick={() => toggleRow(sale.id)}
                                  >
                                    {isOpen ? '▾' : '▸'}
                                  </IconButton>
                                </TableCell>
                                <TableCell>{sale.id}</TableCell>
                                <TableCell>
                                  {formatShortDate(sale.created_at)}
                                </TableCell>
                                <TableCell>{`Empleado #${sale.employee_id}`}</TableCell>
                                <TableCell align="right">
                                  {formatMoney(sale.total)}
                                </TableCell>
                                <TableCell align="right">
                                  {formatQuantity(totalUnits(sale.items))}
                                </TableCell>
                              </TableRow>
                              <TableRow>
                                <TableCell colSpan={6} sx={{ py: 0 }}>
                                  <Collapse in={isOpen} timeout="auto" unmountOnExit>
                                    <Table size="small" sx={{ my: 1 }}>
                                      <TableHead>
                                        <TableRow>
                                          <TableCell>Producto</TableCell>
                                          <TableCell>Categoría</TableCell>
                                          <TableCell align="right">
                                            Cantidad
                                          </TableCell>
                                          <TableCell align="right">
                                            Precio unit.
                                          </TableCell>
                                          <TableCell align="right">
                                            Subtotal
                                          </TableCell>
                                        </TableRow>
                                      </TableHead>
                                      <TableBody>
                                        {sale.items.map((item) => (
                                          <TableRow key={item.id}>
                                            <TableCell>
                                              {item.product_name}
                                            </TableCell>
                                            <TableCell>
                                              {item.category}
                                            </TableCell>
                                            <TableCell align="right">
                                              {formatQuantity(item.quantity)}
                                            </TableCell>
                                            <TableCell align="right">
                                              {formatMoney(item.unit_price)}
                                            </TableCell>
                                            <TableCell align="right">
                                              {formatMoney(item.line_total)}
                                            </TableCell>
                                          </TableRow>
                                        ))}
                                      </TableBody>
                                    </Table>
                                  </Collapse>
                                </TableCell>
                              </TableRow>
                            </Fragment>
                          )
                        })
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
