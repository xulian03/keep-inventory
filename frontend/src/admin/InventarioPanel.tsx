import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Snackbar,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material'
import {
  DataGrid,
  type GridColDef,
  type GridPaginationModel,
  type GridRenderCellParams,
} from '@mui/x-data-grid'
import { useAuth } from '../auth/AuthContext'
import {
  fetchCategories,
  fetchProducts,
  formatMoney,
  STATE_COLORS,
  type InventoryState,
  type Product,
  type ProductsResponse,
} from '../api/shared'
import { patchProduct, patchThreshold, type AdminProduct } from './api'

const STATE_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Todas' },
  { value: 'agotado', label: 'Agotado' },
  { value: 'bajo', label: 'Bajo' },
  { value: 'disponible', label: 'Disponible' },
  { value: 'exceso', label: 'Exceso' },
]

const SEARCH_DEBOUNCE_MS = 300

// El backend no soporta orden: todas las columnas quedan sin ordenación.
// La columna de acciones se añade dentro del componente (necesita handlers).
const BASE_COLUMNS: GridColDef<Product>[] = [
  { field: 'id', headerName: 'ID', width: 80, sortable: false },
  { field: 'name', headerName: 'Producto', flex: 1, minWidth: 200, sortable: false },
  { field: 'category', headerName: 'Categoría', width: 170, sortable: false },
  { field: 'brand', headerName: 'Marca', width: 150, sortable: false },
  { field: 'stock', headerName: 'Stock', width: 90, type: 'number', sortable: false },
  {
    field: 'min_threshold',
    headerName: 'Mínimo',
    width: 100,
    type: 'number',
    sortable: false,
  },
  {
    field: 'sale_price',
    headerName: 'Precio',
    width: 120,
    type: 'number',
    sortable: false,
    valueFormatter: (value) => formatMoney(Number(value)),
  },
  {
    field: 'state',
    headerName: 'Estado',
    width: 130,
    sortable: false,
    renderCell: (params: GridRenderCellParams<Product>) => {
      const state = params.row.state
      return (
        <Chip
          size="small"
          label={state}
          sx={{ bgcolor: STATE_COLORS[state], color: '#FFFFFF', fontWeight: 600 }}
        />
      )
    },
  },
]

interface SnackbarState {
  open: boolean
  message: string
  severity: 'success' | 'error'
}

function parseNumber(value: string): number {
  return value.trim() === '' ? Number.NaN : Number(value)
}

function isNonNegativeInt(value: string): boolean {
  const parsed = parseNumber(value)
  return Number.isInteger(parsed) && parsed >= 0
}

export interface InventarioPanelProps {
  initialState?: string
}

export default function InventarioPanel({ initialState }: InventarioPanelProps) {
  const { token } = useAuth()

  // El estado inicial (chip del Resumen) se aplica al montar; como el panel se
  // desmonta al cambiar de pestaña, al volver se reinicia con el valor vigente.
  // Si el usuario cambia el Select, prevalece su elección.
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [stateFilter, setStateFilter] = useState<string>(initialState ?? '')
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 50,
  })
  const [categories, setCategories] = useState<string[]>([])

  // Refresco forzado conservando filtros y página actuales.
  const [refreshKey, setRefreshKey] = useState(0)

  // Diálogo de umbrales.
  const [thresholdTarget, setThresholdTarget] = useState<Product | null>(null)
  const [minThreshold, setMinThreshold] = useState('')
  const [excessThreshold, setExcessThreshold] = useState('')

  // Diálogo de producto (incluye market_price, no presente en Product).
  const [productTarget, setProductTarget] = useState<AdminProduct | null>(null)
  const [productName, setProductName] = useState('')
  const [productSalePrice, setProductSalePrice] = useState('')
  const [productMarketPrice, setProductMarketPrice] = useState('')
  const [productActive, setProductActive] = useState(true)

  const [saving, setSaving] = useState(false)
  const [snackbar, setSnackbar] = useState<SnackbarState>({
    open: false,
    message: '',
    severity: 'success',
  })

  const closeSnackbar = () => setSnackbar((prev) => ({ ...prev, open: false }))

  const [result, setResult] = useState<{
    key: string
    data: ProductsResponse | null
    error: string | null
  }>({ key: '', data: null, error: null })

  const queryKey = token
    ? JSON.stringify({
        search,
        category,
        stateFilter,
        page: paginationModel.page,
        pageSize: paginationModel.pageSize,
        refreshKey,
      })
    : ''

  // La fábrica usa el closure del render actual; el efecto sólo depende de la
  // clave de la petición.
  const factoryRef = useRef<(() => Promise<ProductsResponse>) | null>(null)
  useEffect(() => {
    factoryRef.current = token
      ? () =>
          fetchProducts(token, {
            search: search || undefined,
            category: category || undefined,
            state: stateFilter ? (stateFilter as InventoryState) : undefined,
            is_active: 1,
            page: paginationModel.page + 1,
            page_size: paginationModel.pageSize,
          })
      : null
  })

  // Búsqueda con retardo para no lanzar una petición por pulsación.
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput)
      setPaginationModel((model) => ({ ...model, page: 0 }))
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [searchInput])

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
            error: err instanceof Error ? err.message : 'Error al cargar los productos',
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
        // El catálogo sigue usable aunque no carguen las categorías.
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
    setPaginationModel((model) => ({ ...model, page: 0 }))
  }

  const handleStateChange = (value: string) => {
    setStateFilter(value)
    setPaginationModel((model) => ({ ...model, page: 0 }))
  }

  const handleSearchChange = (value: string) => {
    setSearchInput(value)
  }

  const openThresholdDialog = (row: Product) => {
    setThresholdTarget(row)
    setMinThreshold(String(row.min_threshold))
    setExcessThreshold(String(row.excess_threshold))
  }

  const closeThresholdDialog = () => {
    if (saving) return
    setThresholdTarget(null)
  }

  const thresholdValid =
    isNonNegativeInt(minThreshold) && isNonNegativeInt(excessThreshold)

  const handleSaveThreshold = async () => {
    if (!token || !thresholdTarget || saving || !thresholdValid) return
    setSaving(true)
    try {
      await patchThreshold(token, thresholdTarget.id, {
        min_threshold: parseNumber(minThreshold),
        excess_threshold: parseNumber(excessThreshold),
      })
      setSnackbar({
        open: true,
        message: `Umbrales de "${thresholdTarget.name}" actualizados`,
        severity: 'success',
      })
      setThresholdTarget(null)
      // Conserva filtros y página; el semáforo se recalcula al recargar.
      setRefreshKey((key) => key + 1)
    } catch (err: unknown) {
      setSnackbar({
        open: true,
        message:
          err instanceof Error ? err.message : 'No se pudieron guardar los umbrales',
        severity: 'error',
      })
    } finally {
      setSaving(false)
    }
  }

  const openProductDialog = (row: AdminProduct) => {
    setProductTarget(row)
    setProductName(row.name)
    setProductSalePrice(String(row.sale_price))
    setProductMarketPrice(String(row.market_price))
    setProductActive(row.is_active)
  }

  const closeProductDialog = () => {
    if (saving) return
    setProductTarget(null)
  }

  const productValid =
    productName.trim() !== '' &&
    parseNumber(productSalePrice) > 0 &&
    parseNumber(productMarketPrice) >= 0

  const handleSaveProduct = async () => {
    if (!token || !productTarget || saving || !productValid) return
    setSaving(true)
    try {
      await patchProduct(token, productTarget.id, {
        name: productName.trim(),
        sale_price: parseNumber(productSalePrice),
        market_price: parseNumber(productMarketPrice),
        is_active: productActive,
      })
      setSnackbar({
        open: true,
        message: `Producto "${productName.trim()}" actualizado`,
        severity: 'success',
      })
      setProductTarget(null)
      setRefreshKey((key) => key + 1)
    } catch (err: unknown) {
      setSnackbar({
        open: true,
        message:
          err instanceof Error ? err.message : 'No se pudo guardar el producto',
        severity: 'error',
      })
    } finally {
      setSaving(false)
    }
  }

  const columns: GridColDef<Product>[] = [
    ...BASE_COLUMNS,
    {
      field: 'actions',
      headerName: 'Acciones',
      width: 220,
      sortable: false,
      filterable: false,
      renderCell: (params: GridRenderCellParams<Product>) => (
        <Stack direction="row" spacing={0.5}>
          <Button size="small" onClick={() => openThresholdDialog(params.row)}>
            Editar umbral
          </Button>
          <Button
            size="small"
            onClick={() => openProductDialog(params.row as AdminProduct)}
          >
            Editar producto
          </Button>
        </Stack>
      ),
    },
  ]

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
            <TextField
              label="Buscar"
              size="small"
              value={searchInput}
              onChange={(event) => handleSearchChange(event.target.value)}
              placeholder="Nombre o marca"
              sx={{ minWidth: 220 }}
            />

            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel id="inventario-category-label">Categoría</InputLabel>
              <Select
                labelId="inventario-category-label"
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

            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel id="inventario-state-label">Estado</InputLabel>
              <Select
                labelId="inventario-state-label"
                label="Estado"
                value={stateFilter}
                onChange={(event) => handleStateChange(event.target.value)}
              >
                {STATE_OPTIONS.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
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
              Inventario
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Catálogo activo ({data?.total.toLocaleString('es-ES') ?? 0} productos)
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

      <Dialog
        open={thresholdTarget !== null}
        onClose={closeThresholdDialog}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Editar umbral</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="Producto"
              value={thresholdTarget?.name ?? ''}
              size="small"
              disabled
              fullWidth
            />
            <TextField
              label="Umbral mínimo"
              type="number"
              size="small"
              value={minThreshold}
              onChange={(event) => setMinThreshold(event.target.value)}
              error={minThreshold !== '' && !isNonNegativeInt(minThreshold)}
              slotProps={{ htmlInput: { min: 0, step: 1 } }}
              fullWidth
            />
            <TextField
              label="Umbral de exceso"
              type="number"
              size="small"
              value={excessThreshold}
              onChange={(event) => setExcessThreshold(event.target.value)}
              error={excessThreshold !== '' && !isNonNegativeInt(excessThreshold)}
              slotProps={{ htmlInput: { min: 0, step: 1 } }}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeThresholdDialog} disabled={saving}>
            Cancelar
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveThreshold}
            disabled={saving || !thresholdValid}
          >
            {saving ? 'Guardando…' : 'Guardar'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={productTarget !== null}
        onClose={closeProductDialog}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Editar producto</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="Nombre"
              size="small"
              value={productName}
              onChange={(event) => setProductName(event.target.value)}
              error={productName.trim() === ''}
              fullWidth
            />
            <TextField
              label="Precio de venta"
              type="number"
              size="small"
              value={productSalePrice}
              onChange={(event) => setProductSalePrice(event.target.value)}
              error={
                productSalePrice !== '' && !(parseNumber(productSalePrice) > 0)
              }
              slotProps={{ htmlInput: { min: 0, step: 0.01 } }}
              fullWidth
            />
            <TextField
              label="Precio de mercado"
              type="number"
              size="small"
              value={productMarketPrice}
              onChange={(event) => setProductMarketPrice(event.target.value)}
              error={
                productMarketPrice !== '' &&
                !(parseNumber(productMarketPrice) >= 0)
              }
              slotProps={{ htmlInput: { min: 0, step: 0.01 } }}
              fullWidth
            />
            <FormControlLabel
              control={
                <Switch
                  checked={productActive}
                  onChange={(event) => setProductActive(event.target.checked)}
                />
              }
              label="Activo"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeProductDialog} disabled={saving}>
            Cancelar
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveProduct}
            disabled={saving || !productValid}
          >
            {saving ? 'Guardando…' : 'Guardar'}
          </Button>
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
    </Stack>
  )
}
