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
import { fetchProducts, formatMoney } from '../api/shared'
import OrderDialog from './OrderDialog'
import {
  fetchPurchaseOrder,
  fetchPurchaseOrders,
  fetchSuppliers,
  sendPurchaseOrder,
  cancelPurchaseOrder,
  deletePurchaseOrder,
  type Supplier,
} from './api'
import {
  type OrderStatus,
  type PurchaseOrder,
  type PurchaseOrderDetail,
  type PurchaseOrdersResponse,
} from '../empleado/api'

// Colores coherentes con STATE_COLORS (api/shared): gris/ámbar/verde/rojo.
const ORDER_STATUS_COLORS: Record<OrderStatus, string> = {
  borrador: '#9CA3AF',
  enviada: '#F59E0B',
  recibida: '#10B981',
  cancelada: '#EF4444',
}

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Todas' },
  { value: 'borrador', label: 'Borrador' },
  { value: 'enviada', label: 'Enviada' },
  { value: 'recibida', label: 'Recibida' },
  { value: 'cancelada', label: 'Cancelada' },
]

const CARD_SX = {
  borderRadius: '14px',
  borderColor: '#E5E7EB',
  boxShadow: 'none',
} as const

type ConfirmAction = 'send' | 'cancel' | 'delete'

interface ConfirmState {
  action: ConfirmAction
  order: PurchaseOrder
}

interface SnackbarState {
  open: boolean
  message: string
  severity: 'success' | 'error'
}

// El backend sólo devuelve fechas ISO; para la tabla se muestra la parte corta.
function formatShortDate(value: string | null): string {
  if (!value) return '—'
  return value.slice(0, 10)
}

export default function OrdenesPanel() {
  const { token } = useAuth()

  const [statusFilter, setStatusFilter] = useState('')
  const [supplierFilter, setSupplierFilter] = useState('')
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 50,
  })
  const [refreshKey, setRefreshKey] = useState(0)
  // Marca la fila cuyo "Editar" se pulsó (se resalta mientras el diálogo está abierto).
  const [editingId, setEditingId] = useState<number | null>(null)
  // Diálogo de alta/edición de borradores (OrderDialog).
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogOrder, setDialogOrder] = useState<PurchaseOrder | null>(null)

  const [result, setResult] = useState<{
    key: string
    data: PurchaseOrdersResponse | null
    error: string | null
  }>({ key: '', data: null, error: null })

  const queryKey = token
    ? JSON.stringify({
        statusFilter,
        supplierFilter,
        page: paginationModel.page,
        pageSize: paginationModel.pageSize,
        refreshKey,
      })
    : ''

  // La fábrica usa el closure del render actual; el efecto sólo depende de la
  // clave de la petición.
  const factoryRef = useRef<(() => Promise<PurchaseOrdersResponse>) | null>(null)
  useEffect(() => {
    factoryRef.current = token
      ? () =>
          fetchPurchaseOrders(token, {
            status: statusFilter ? (statusFilter as OrderStatus) : undefined,
            supplier_id: supplierFilter ? Number(supplierFilter) : undefined,
            page: paginationModel.page + 1,
            page_size: paginationModel.pageSize,
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
              err instanceof Error ? err.message : 'Error al cargar las órdenes de compra',
          })
      })
    return () => {
      active = false
    }
  }, [queryKey])

  useEffect(() => {
    if (!token) return
    let active = true
    fetchSuppliers(token)
      .then((response) => {
        if (active) setSuppliers(response)
      })
      .catch(() => {
        // El listado sigue usable aunque no carguen los proveedores.
      })
    return () => {
      active = false
    }
  }, [token])

  const fresh = result.key === queryKey
  const data = fresh ? result.data : null
  const error = fresh ? result.error : null
  const loading = queryKey !== '' && !fresh

  const supplierName = (supplierId: number): string => {
    const found = suppliers.find((item) => item.id === supplierId)
    return found ? found.name : `Proveedor #${supplierId}`
  }

  // --- confirmaciones de enviar / cancelar / eliminar ---
  const [confirm, setConfirm] = useState<ConfirmState | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [snackbar, setSnackbar] = useState<SnackbarState>({
    open: false,
    message: '',
    severity: 'success',
  })

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }))

  // --- diálogo "Ver" detalle ---
  const [viewOrder, setViewOrder] = useState<PurchaseOrder | null>(null)
  const [detail, setDetail] = useState<PurchaseOrderDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)
  // El detalle de la orden sólo trae product_id; se resuelven los nombres con
  // el filtro `ids` del catálogo (incluye inactivos) y hay fallback si falla.
  const [productNames, setProductNames] = useState<Record<number, string>>({})

  const openView = (row: PurchaseOrder) => {
    setViewOrder(row)
    setDetail(null)
    setDetailError(null)
    setProductNames({})
    if (!token) return
    setDetailLoading(true)
    fetchPurchaseOrder(token, row.id)
      .then((response) => {
        setDetail(response)
        const ids = response.items.map((item) => item.product_id)
        if (ids.length === 0) return
        fetchProducts(token, {
          ids: ids.join(','),
          is_active: undefined,
          page_size: 100,
        })
          .then((products) => {
            const names: Record<number, string> = {}
            products.items.forEach((product) => {
              names[product.id] = product.name
            })
            setProductNames(names)
          })
          .catch(() => {
            // Se conserva el fallback "Producto #id".
          })
      })
      .catch((err: unknown) =>
        setDetailError(
          err instanceof Error ? err.message : 'Error al cargar el detalle de la orden',
        ),
      )
      .finally(() => setDetailLoading(false))
  }

  const closeView = () => {
    setViewOrder(null)
    setDetail(null)
    setDetailError(null)
    setDetailLoading(false)
    setProductNames({})
  }

  const openNewOrder = () => {
    setDialogOrder(null)
    setDialogOpen(true)
  }

  const openEditOrder = (row: PurchaseOrder) => {
    setEditingId(row.id)
    setDialogOrder(row)
    setDialogOpen(true)
  }

  const closeOrderDialog = () => {
    setDialogOpen(false)
    setDialogOrder(null)
    setEditingId(null)
  }

  const handleOrderSaved = () => {
    setRefreshKey((key) => key + 1)
  }

  const handleStatusChange = (value: string) => {
    setStatusFilter(value)
    setPaginationModel((model) => ({ ...model, page: 0 }))
  }

  const handleSupplierChange = (value: string) => {
    setSupplierFilter(value)
    setPaginationModel((model) => ({ ...model, page: 0 }))
  }

  const openConfirm = (action: ConfirmAction, order: PurchaseOrder) => {
    setConfirm({ action, order })
  }

  const closeConfirm = () => {
    setConfirm(null)
    setConfirming(false)
  }

  const runConfirm = async () => {
    if (!token || !confirm || confirming) return
    const { action, order } = confirm
    setConfirming(true)
    try {
      if (action === 'send') {
        await sendPurchaseOrder(token, order.id)
      } else if (action === 'cancel') {
        await cancelPurchaseOrder(token, order.id)
      } else {
        await deletePurchaseOrder(token, order.id)
      }
      setSnackbar({
        open: true,
        message:
          action === 'send'
            ? `Orden #${order.id} enviada`
            : action === 'cancel'
              ? `Orden #${order.id} cancelada`
              : `Orden #${order.id} eliminada`,
        severity: 'success',
      })
      closeConfirm()
      // Conserva filtros y página; sólo se relanza la misma consulta.
      setRefreshKey((key) => key + 1)
    } catch (err: unknown) {
      setSnackbar({
        open: true,
        message: err instanceof Error ? err.message : 'No se pudo completar la acción',
        severity: 'error',
      })
      setConfirming(false)
    }
  }

  const columns: GridColDef<PurchaseOrder>[] = [
    { field: 'id', headerName: 'ID', width: 80, sortable: false },
    {
      field: 'supplier_id',
      headerName: 'Proveedor',
      width: 200,
      sortable: false,
      valueGetter: (_value, row) => supplierName(row.supplier_id),
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
      field: 'created_at',
      headerName: 'Creada',
      width: 120,
      sortable: false,
      valueFormatter: (value) => formatShortDate(String(value)),
    },
    {
      field: 'expected_date',
      headerName: 'Esperada',
      width: 120,
      sortable: false,
      valueFormatter: (value) => formatShortDate(value ? String(value) : null),
    },
    {
      field: 'total',
      headerName: 'Total',
      width: 130,
      type: 'number',
      sortable: false,
      valueFormatter: (value) => formatMoney(Number(value)),
    },
    {
      field: 'item_count',
      headerName: 'N ítems',
      width: 90,
      type: 'number',
      sortable: false,
    },
    {
      field: 'actions',
      headerName: 'Acciones',
      width: 260,
      sortable: false,
      filterable: false,
      renderCell: (params: GridRenderCellParams<PurchaseOrder>) => {
        const row = params.row
        return (
          <Stack direction="row" spacing={0.5}>
            {row.status === 'borrador' && (
              <>
                <Button size="small" onClick={() => openEditOrder(row)}>
                  Editar
                </Button>
                <Button size="small" onClick={() => openConfirm('send', row)}>
                  Enviar
                </Button>
                <Button
                  size="small"
                  color="error"
                  onClick={() => openConfirm('delete', row)}
                >
                  Eliminar
                </Button>
              </>
            )}
            {row.status === 'enviada' && (
              <>
                <Button
                  size="small"
                  color="warning"
                  onClick={() => openConfirm('cancel', row)}
                >
                  Cancelar
                </Button>
                <Button size="small" onClick={() => openView(row)}>
                  Ver
                </Button>
              </>
            )}
            {(row.status === 'recibida' || row.status === 'cancelada') && (
              <Button size="small" onClick={() => openView(row)}>
                Ver
              </Button>
            )}
          </Stack>
        )
      },
    },
  ]

  const confirmOrder = confirm?.order ?? null

  return (
    <Stack spacing={3}>
      <Card variant="outlined" sx={CARD_SX}>
        <CardContent>
          <Stack
            direction={{ xs: 'column', md: 'row' }}
            spacing={2}
            useFlexGap
            sx={{ alignItems: { md: 'center' }, flexWrap: 'wrap' }}
          >
            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel id="ordenes-status-label">Estado</InputLabel>
              <Select
                labelId="ordenes-status-label"
                label="Estado"
                value={statusFilter}
                onChange={(event) => handleStatusChange(event.target.value)}
              >
                {STATUS_OPTIONS.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 220 }}>
              <InputLabel id="ordenes-supplier-label">Proveedor</InputLabel>
              <Select
                labelId="ordenes-supplier-label"
                label="Proveedor"
                value={supplierFilter}
                onChange={(event) => handleSupplierChange(event.target.value)}
              >
                <MenuItem value="">Todos</MenuItem>
                {suppliers.map((supplier) => (
                  <MenuItem key={supplier.id} value={String(supplier.id)}>
                    {supplier.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Button
              variant="contained"
              onClick={openNewOrder}
              sx={{ ml: { md: 'auto' } }}
            >
              Nueva orden
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {error ? (
        <Alert severity="error">{error}</Alert>
      ) : (
        <Card variant="outlined" sx={CARD_SX}>
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Órdenes de compra
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Órdenes registradas ({data?.total.toLocaleString('es-ES') ?? 0})
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
                getRowClassName={(params) =>
                  params.row.id === editingId ? 'ordenes-row-editing' : ''
                }
                sx={{ '& .ordenes-row-editing': { backgroundColor: '#F5F3FF' } }}
              />
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Confirmación de enviar / cancelar / eliminar */}
      <Dialog open={confirm !== null} onClose={closeConfirm} fullWidth maxWidth="xs">
        <DialogTitle>
          {confirm?.action === 'send'
            ? 'Enviar orden'
            : confirm?.action === 'cancel'
              ? 'Cancelar orden'
              : 'Eliminar orden'}
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2">
            {confirm?.action === 'send'
              ? `¿Enviar la orden #${confirmOrder?.id} al proveedor? Una vez enviada no podrá editarse.`
              : confirm?.action === 'cancel'
                ? `¿Cancelar la orden #${confirmOrder?.id}?`
                : `¿Eliminar la orden #${confirmOrder?.id}? Esta acción no se puede deshacer.`}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeConfirm} disabled={confirming}>
            Volver
          </Button>
          <Button
            variant="contained"
            color={confirm?.action === 'delete' ? 'error' : 'primary'}
            onClick={runConfirm}
            disabled={confirming}
          >
            {confirming
              ? 'Procesando…'
              : confirm?.action === 'send'
                ? 'Enviar'
                : confirm?.action === 'cancel'
                  ? 'Cancelar orden'
                  : 'Eliminar'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Detalle "Ver" */}
      <Dialog open={viewOrder !== null} onClose={closeView} fullWidth maxWidth="sm">
        <DialogTitle>Orden #{viewOrder?.id}</DialogTitle>
        <DialogContent dividers>
          {detailLoading ? (
            <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
              <CircularProgress size={28} />
            </Box>
          ) : detailError ? (
            <Alert severity="error">{detailError}</Alert>
          ) : detail ? (
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">
                {supplierName(detail.supplier_id)} · {detail.status} · Creada{' '}
                {formatShortDate(detail.created_at)} · Esperada{' '}
                {formatShortDate(detail.expected_date)}
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
                      {productNames[item.product_id] ??
                        `Producto #${item.product_id}`}{' '}
                      · {item.quantity} × {formatMoney(item.unit_cost)}
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
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeView}>Cerrar</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={closeSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity={snackbar.severity}
          variant="filled"
          onClose={closeSnackbar}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>

      <OrderDialog
        open={dialogOpen}
        order={dialogOrder}
        onClose={closeOrderDialog}
        onSaved={handleOrderSaved}
      />
    </Stack>
  )
}
