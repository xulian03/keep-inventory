import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useAuth } from '../auth/AuthContext'
import {
  fetchProducts,
  formatMoney,
  STATE_COLORS,
  type Product,
  type ProductsResponse,
} from '../api/shared'
import { createSale, type SaleCreatedResponse } from './api'

const SEARCH_DEBOUNCE_MS = 300
const PAGE_SIZE = 10

const CARD_SX = { borderRadius: '14px', borderColor: '#E5E7EB', boxShadow: 'none' } as const

interface CartLine {
  product: Product
  quantity: number
}

interface SnackbarState {
  open: boolean
  message: string
  severity: 'success' | 'error'
}

export default function RegistrarVentaPanel() {
  const { token } = useAuth()

  // --- buscador ---
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [result, setResult] = useState<{
    key: string
    data: ProductsResponse | null
    error: string | null
  }>({ key: '', data: null, error: null })

  const queryKey = token ? JSON.stringify({ search, refreshKey }) : ''

  const factoryRef = useRef<(() => Promise<ProductsResponse>) | null>(null)
  useEffect(() => {
    factoryRef.current = token
      ? () =>
          fetchProducts(token, {
            search: search || undefined,
            // Sin filtro is_active: los inactivos se muestran deshabilitados.
            is_active: undefined,
            page: 1,
            page_size: PAGE_SIZE,
          })
      : null
  })

  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput), SEARCH_DEBOUNCE_MS)
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
            error: err instanceof Error ? err.message : 'Error al buscar productos',
          })
      })
    return () => {
      active = false
    }
  }, [queryKey])

  const fresh = result.key === queryKey
  const products = fresh ? result.data?.items ?? [] : []
  const searchError = fresh ? result.error : null
  const searchLoading = queryKey !== '' && !fresh

  // --- carrito ---
  const [cart, setCart] = useState<CartLine[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [ticket, setTicket] = useState<SaleCreatedResponse | null>(null)
  const [snackbar, setSnackbar] = useState<SnackbarState>({
    open: false,
    message: '',
    severity: 'success',
  })

  const total = cart.reduce(
    (sum, line) => sum + line.product.sale_price * line.quantity,
    0,
  )

  const addToCart = (product: Product) => {
    if (!product.is_active || product.stock <= 0) return
    setTicket(null)
    setCart((prev) => {
      const existing = prev.find((line) => line.product.id === product.id)
      if (existing) {
        return prev.map((line) =>
          line.product.id === product.id
            ? { ...line, quantity: Math.min(line.quantity + 1, product.stock) }
            : line,
        )
      }
      return [...prev, { product, quantity: 1 }]
    })
  }

  const setQuantity = (productId: number, value: number) => {
    setCart((prev) =>
      prev.map((line) =>
        line.product.id === productId
          ? {
              ...line,
              quantity: Math.min(Math.max(value, 1), line.product.stock),
            }
          : line,
      ),
    )
  }

  const removeLine = (productId: number) => {
    setCart((prev) => prev.filter((line) => line.product.id !== productId))
  }

  const handleCheckout = async () => {
    if (!token || cart.length === 0 || submitting) return
    setSubmitting(true)
    setTicket(null)
    try {
      const response = await createSale(
        token,
        cart.map((line) => ({ product_id: line.product.id, quantity: line.quantity })),
      )
      setTicket(response)
      setCart([])
      setRefreshKey((key) => key + 1)
      setSnackbar({
        open: true,
        message: `Venta #${response.venta.id} registrada`,
        severity: 'success',
      })
    } catch (err: unknown) {
      setSnackbar({
        open: true,
        message: err instanceof Error ? err.message : 'Error al registrar la venta',
        severity: 'error',
      })
    } finally {
      setSubmitting(false)
    }
  }

  // Nombre de producto para el stock resultante del ticket.
  const productName = (productId: number): string =>
    ticket?.venta.items.find((item) => item.product_id === productId)?.product_name ??
    `Producto #${productId}`

  return (
    <Stack spacing={3}>
      <Card variant="outlined" sx={CARD_SX}>
        <CardContent>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Buscar producto
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Pulsa un resultado para añadirlo al carrito.
          </Typography>

          <TextField
            fullWidth
            label="Buscar"
            size="small"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Nombre o marca"
          />

          <Box sx={{ mt: 2 }}>
            {searchLoading ? (
              <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
                <CircularProgress size={28} />
              </Box>
            ) : searchError ? (
              <Alert severity="error">{searchError}</Alert>
            ) : products.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                Sin resultados.
              </Typography>
            ) : (
              <Stack spacing={1}>
                {products.map((product) => {
                  const disabled = !product.is_active || product.stock <= 0
                  return (
                    <Box
                      key={product.id}
                      role="button"
                      tabIndex={disabled ? -1 : 0}
                      onClick={() => addToCart(product)}
                      sx={{
                        p: 1.5,
                        border: '1px solid #E5E7EB',
                        borderRadius: '10px',
                        cursor: disabled ? 'not-allowed' : 'pointer',
                        opacity: disabled ? 0.55 : 1,
                        '&:hover': disabled
                          ? undefined
                          : { borderColor: '#7C3AED', bgcolor: '#FAF5FF' },
                      }}
                    >
                      <Stack
                        direction={{ xs: 'column', sm: 'row' }}
                        spacing={1}
                        useFlexGap
                        sx={{ alignItems: { sm: 'center' }, flexWrap: 'wrap' }}
                      >
                        <Box sx={{ flex: 1, minWidth: 180 }}>
                          <Typography variant="body1" sx={{ fontWeight: 600 }}>
                            {product.name}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {product.brand} · {product.category}
                          </Typography>
                        </Box>
                        <Typography variant="body2" sx={{ minWidth: 90 }}>
                          {formatMoney(product.sale_price)}
                        </Typography>
                        <Typography variant="body2" sx={{ minWidth: 90 }}>
                          Stock: {product.stock}
                        </Typography>
                        <Chip
                          size="small"
                          label={product.state}
                          sx={{
                            bgcolor: STATE_COLORS[product.state],
                            color: '#FFFFFF',
                            fontWeight: 600,
                          }}
                        />
                        {!product.is_active && (
                          <Chip
                            size="small"
                            label="inactivo"
                            sx={{ bgcolor: '#9CA3AF', color: '#FFFFFF', fontWeight: 600 }}
                          />
                        )}
                      </Stack>
                    </Box>
                  )
                })}
              </Stack>
            )}
          </Box>
        </CardContent>
      </Card>

      <Card variant="outlined" sx={CARD_SX}>
        <CardContent>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Carrito
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {cart.length === 0 ? 'Vacío.' : `${cart.length} línea(s)`}
          </Typography>

          {cart.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              Añade productos desde el buscador.
            </Typography>
          ) : (
            <Stack spacing={2} divider={<Divider flexItem />}>
              {cart.map((line) => (
                <Stack
                  key={line.product.id}
                  direction={{ xs: 'column', sm: 'row' }}
                  spacing={1}
                  useFlexGap
                  sx={{ alignItems: { sm: 'center' }, flexWrap: 'wrap' }}
                >
                  <Box sx={{ flex: 1, minWidth: 160 }}>
                    <Typography variant="body1" sx={{ fontWeight: 600 }}>
                      {line.product.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {formatMoney(line.product.sale_price)} · máx {line.product.stock}
                    </Typography>
                  </Box>

                  <TextField
                    type="number"
                    size="small"
                    label="Cantidad"
                    value={line.quantity}
                    onChange={(event) => {
                      const next = Number.parseInt(event.target.value, 10)
                      if (!Number.isNaN(next)) setQuantity(line.product.id, next)
                    }}
                    sx={{ width: 120 }}
                  />

                  <Typography variant="body1" sx={{ minWidth: 100, fontWeight: 600 }}>
                    {formatMoney(line.product.sale_price * line.quantity)}
                  </Typography>

                  <Button
                    size="small"
                    color="error"
                    onClick={() => removeLine(line.product.id)}
                  >
                    Quitar
                  </Button>
                </Stack>
              ))}
            </Stack>
          )}

          <Divider sx={{ my: 2 }} />

          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={2}
            useFlexGap
            sx={{ alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
          >
            <Box>
              <Typography variant="body2" color="text.secondary">
                Total
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700 }}>
                {formatMoney(total)}
              </Typography>
            </Box>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
              {submitting && <CircularProgress size={22} />}
              <Button
                variant="contained"
                disabled={cart.length === 0 || submitting}
                onClick={handleCheckout}
              >
                Cobrar
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {ticket && (
        <Card variant="outlined" sx={CARD_SX}>
          <CardContent>
            <Stack
              direction="row"
              spacing={2}
              sx={{ alignItems: 'center', justifyContent: 'space-between' }}
            >
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Venta #{ticket.venta.id} registrada
              </Typography>
              <Button size="small" onClick={() => setTicket(null)}>
                Cerrar
              </Button>
            </Stack>

            <Stack spacing={1} sx={{ mt: 2 }}>
              {ticket.venta.items.map((item) => (
                <Stack
                  key={item.id}
                  direction="row"
                  spacing={2}
                  sx={{ justifyContent: 'space-between' }}
                >
                  <Typography variant="body2">
                    {item.quantity} × {item.product_name}
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {formatMoney(item.line_total)}
                  </Typography>
                </Stack>
              ))}
            </Stack>

            <Divider sx={{ my: 2 }} />

            <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                Total
              </Typography>
              <Typography variant="body1" sx={{ fontWeight: 700 }}>
                {formatMoney(ticket.venta.total)}
              </Typography>
            </Stack>

            <Typography variant="subtitle2" sx={{ mt: 2, fontWeight: 600 }}>
              Stock resultante
            </Typography>
            <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1, flexWrap: 'wrap' }}>
              {ticket.stock.map((entry) => (
                <Chip
                  key={entry.product_id}
                  size="small"
                  label={`${productName(entry.product_id)}: ${entry.stock}`}
                  variant="outlined"
                />
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}

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
