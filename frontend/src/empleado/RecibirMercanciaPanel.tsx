import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Snackbar,
  Stack,
  Typography,
} from '@mui/material'
import {
  DataGrid,
  type GridColDef,
  type GridPaginationModel,
  type GridRenderCellParams,
} from '@mui/x-data-grid'
import { useAuth } from '../auth/AuthContext'
import { formatMoney } from '../api/shared'
import {
  fetchPurchaseOrder,
  fetchPurchaseOrders,
  receivePurchaseOrder,
  type OrderStatus,
  type PurchaseOrder,
  type PurchaseOrderDetail,
  type PurchaseOrdersResponse,
} from './api'

// Colores coherentes con STATE_COLORS (api/shared): gris/ámbar/verde/rojo.
const ORDER_STATUS_COLORS: Record<OrderStatus, string> = {
  borrador: '#9CA3AF',
  enviada: '#F59E0B',
  recibida: '#10B981',
  cancelada: '#EF4444',
}

const STATUS_OPTIONS: { value: OrderStatus; label: string }[] = [
  { value: 'borrador', label: 'Borrador' },
  { value: 'enviada', label: 'Enviada' },
  { value: 'recibida', label: 'Recibida' },
  { value: 'cancelada', label: 'Cancelada' },
]

const CARD_SX = { borderRadius: '14px', borderColor: '#E5E7EB', boxShadow: 'none' } as const

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('es-ES')
}

interface SnackbarState {
  open: boolean
  message: string
  severity: 'success' | 'error'
}

export default function RecibirMercanciaPanel() {
  const { token } = useAuth()

  const [statusFilter, setStatusFilter] = useState<OrderStatus>('enviada')
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 50,
  })
  const [refreshKey, setRefreshKey] = useState(0)

  const [result, setResult] = useState<{
    key: string
    data: PurchaseOrdersResponse | null
    error: string | null
  }>({ key: '', data: null, error: null })

  const queryKey = token
    ? JSON.stringify({
        statusFilter,
        page: paginationModel.page,
        pageSize: paginationModel.pageSize,
        refreshKey,
      })
    : ''

  const factoryRef = useRef<(() => Promise<PurchaseOrdersResponse>) | null>(null)
  useEffect(() => {
    factoryRef.current = token
      ? () =>
          fetchPurchaseOrders(
            token,
            statusFilter,
            paginationModel.page + 1,
            paginationModel.pageSize,
          )
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
              err instanceof Error ? err.message : 'Error al cargar las órdenes de compra',
          })
      })
    return () => {
      active = false
    }
  }, [queryKey])

  const fresh = result.key === queryKey
  const data = fresh ? result.data : null
  const error = fresh ? result.error : null
  const loading = queryKey !== '' && !fresh

  // --- diálogo de recepción ---
  const [order, setOrder] = useState<PurchaseOrder | null>(null)
  const [detail, setDetail] = useState<PurchaseOrderDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [dialogError, setDialogError] = useState<string | null>(null)
  const [receiving, setReceiving] = useState(false)
  const [snackbar, setSnackbar] = useState<SnackbarState>({
    open: false,
    message: '',
    severity: 'success',
  })

  const handleStatusChange = (value: OrderStatus) => {
    setStatusFilter(value)
    setPaginationModel((model) => ({ ...model, page: 0 }))
  }

  const openReceive = (row: PurchaseOrder) => {
    setOrder(row)
    setDetail(null)
    setDialogError(null)
    setDetailLoading(true)
    if (!token) return
    fetchPurchaseOrder(token, row.id)
      .then((response) => setDetail(response))
      .catch((err: unknown) =>
        setDialogError(
          err instanceof Error ? err.message : 'Error al cargar el detalle de la orden',
        ),
      )
      .finally(() => setDetailLoading(false))
  }

  const closeReceive = () => {
    setOrder(null)
    setDetail(null)
    setDialogError(null)
    setReceiving(false)
  }

  const confirmReceive = async () => {
    if (!token || !order || receiving) return
    setReceiving(true)
    setDialogError(null)
    try {
      const response = await receivePurchaseOrder(token, order.id)
      setSnackbar({
        open: true,
        message: `Orden #${response.id} recibida: stock actualizado`,
        severity: 'success',
      })
      setRefreshKey((key) => key + 1)
      closeReceive()
    } catch (err: unknown) {
      setDialogError(
        err instanceof Error ? err.message : 'Error al recibir la orden',
      )
      setReceiving(false)
    }
  }

  const columns: GridColDef<PurchaseOrder>[] = [
    { field: 'id', headerName: 'ID', width: 80, sortable: false },
    {
      field: 'supplier_id',
      headerName: 'Proveedor',
      width: 140,
      sortable: false,
      valueGetter: (_value, row) => `Proveedor #${row.supplier_id}`,
    },
    {
      field: 'item_count',
      headerName: 'Artículos',
      width: 110,
      type: 'number',
      sortable: false,
    },
    {
      field: 'total',
      headerName: 'Total',
      width: 120,
      type: 'number',
      sortable: false,
      valueFormatter: (value) => formatMoney(Number(value)),
    },
    {
      field: 'expected_date',
      headerName: 'Fecha esperada',
      width: 150,
      sortable: false,
      valueFormatter: (value) => formatDate(String(value)),
    },
    {
      field: 'status',
      headerName: 'Estado',
      width: 130,
      sortable: false,
      renderCell: (params: GridRenderCellParams<PurchaseOrder>) => (
        <Chip
          size="small"
          label={params.row.status}
          sx={{
            bgcolor: ORDER_STATUS_COLORS[params.row.status],
            color: '#FFFFFF',
            fontWeight: 600,
          }}
        />
      ),
    },
    {
      field: 'actions',
      headerName: 'Acciones',
      width: 120,
      sortable: false,
      filterable: false,
      renderCell: (params: GridRenderCellParams<PurchaseOrder>) =>
        params.row.status === 'enviada' ? (
          <Button size="small" onClick={() => openReceive(params.row)}>
            Recibir
          </Button>
        ) : null,
    },
  ]

  return (
    <Stack spacing={3}>
      <Card variant="outlined" sx={CARD_SX}>
        <CardContent>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel id="recibir-status-label">Estado</InputLabel>
            <Select
              labelId="recibir-status-label"
              label="Estado"
              value={statusFilter}
              onChange={(event) => handleStatusChange(event.target.value as OrderStatus)}
            >
              {STATUS_OPTIONS.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </CardContent>
      </Card>

      {error ? (
        <Alert severity="error">{error}</Alert>
      ) : (
        <Card variant="outlined" sx={CARD_SX}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Recibir mercancía
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Órdenes de compra ({data?.total.toLocaleString('es-ES') ?? 0})
            </Typography>

            <Box sx={{ height: 620, width: '100%' }}>
              <DataGrid
                rows={data?.items ?? []}
                columns={columns}
                loading={loading}
                disableRowSelectionOnClick
                paginationMode="server"
                paginationModel={paginationModel}
                onPaginationModelChange={setPaginationModel}
                pageSizeOptions={[50]}
                rowCount={data?.total ?? 0}
              />
            </Box>
          </CardContent>
        </Card>
      )}

      <Dialog open={order !== null} onClose={closeReceive} fullWidth maxWidth="sm">
        <DialogTitle>
          {order ? `Recibir orden #${order.id}` : 'Recibir orden'}
        </DialogTitle>
        <DialogContent dividers>
          {detailLoading ? (
            <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
              <CircularProgress size={28} />
            </Box>
          ) : dialogError ? (
            <Alert severity="error">{dialogError}</Alert>
          ) : detail ? (
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">
                Proveedor #{detail.supplier_id} · Fecha esperada{' '}
                {formatDate(detail.expected_date)}
              </Typography>

              <Stack spacing={1}>
                {detail.items.map((item) => (
                  <Stack
                    key={item.id}
                    direction="row"
                    spacing={2}
                    sx={{ justifyContent: 'space-between' }}
                  >
                    <Typography variant="body2">
                      Producto #{item.product_id} · {item.quantity} ×{' '}
                      {formatMoney(item.unit_cost)}
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {formatMoney(item.total)}
                    </Typography>
                  </Stack>
                ))}
              </Stack>

              <Divider />

              <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
                <Typography variant="body1" sx={{ fontWeight: 600 }}>
                  Total
                </Typography>
                <Typography variant="body1" sx={{ fontWeight: 700 }}>
                  {formatMoney(detail.total)}
                </Typography>
              </Stack>

              <Alert severity="info">
                Al confirmar se sumará el stock de cada producto.
              </Alert>
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeReceive} disabled={receiving}>
            Cancelar
          </Button>
          <Button
            variant="contained"
            onClick={confirmReceive}
            disabled={receiving || detailLoading || !detail || dialogError !== null}
          >
            {receiving ? 'Recibiendo…' : 'Confirmar recepción'}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity={snackbar.severity}
          variant="filled"
          onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Stack>
  )
}
