import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
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
  type InventoryState,
  type Product,
  type ProductsResponse,
} from './api'

// Colores del semáforo §7 (agotado/bajo/disponible/exceso).
const STATE_COLORS: Record<InventoryState, string> = {
  agotado: '#EF4444',
  bajo: '#F59E0B',
  disponible: '#10B981',
  exceso: '#3B82F6',
}

const STATE_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Todas' },
  { value: 'agotado', label: 'Agotado' },
  { value: 'bajo', label: 'Bajo' },
  { value: 'disponible', label: 'Disponible' },
  { value: 'exceso', label: 'Exceso' },
]

const SEARCH_DEBOUNCE_MS = 300

// El backend no soporta orden: todas las columnas quedan sin ordenación.
const columns: GridColDef<Product>[] = [
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
    </Stack>
  )
}
