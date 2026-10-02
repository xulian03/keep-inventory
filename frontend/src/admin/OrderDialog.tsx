import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Autocomplete,
  Box,
  Button,
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
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useAuth } from '../auth/AuthContext'
import { fetchProducts, formatMoney, type Product } from '../api/shared'
import {
  createPurchaseOrder,
  fetchPurchaseOrder,
  fetchSuppliers,
  updatePurchaseOrder,
  type PurchaseOrderItemIn,
  type Supplier,
} from './api'
import type { PurchaseOrder } from '../empleado/api'

interface ProductOption {
  id: number
  name: string
  is_active: boolean
}

interface OrderLine {
  key: number
  product: ProductOption | null
  quantity: string
  unitCost: string
}

let lineSeq = 0

function nextKey(): number {
  lineSeq += 1
  return lineSeq
}

function createLine(): OrderLine {
  return { key: nextKey(), product: null, quantity: '1', unitCost: '0' }
}

function toOption(product: Product): ProductOption {
  return { id: product.id, name: product.name, is_active: product.is_active }
}

const SEARCH_DEBOUNCE_MS = 300

interface ProductAutocompleteProps {
  token: string
  supplierId: number | null
  value: ProductOption | null
  disabled: boolean
  onChange: (product: ProductOption | null) => void
}

// Autocomplete de productos del proveedor elegido: busca en servidor con
// supplier_id + search + is_active=1 y conserva el valor aunque no esté entre
// las opciones (p. ej. un producto ya inactivo al editar).
function ProductAutocomplete({
  token,
  supplierId,
  value,
  disabled,
  onChange,
}: ProductAutocompleteProps) {
  const [input, setInput] = useState('')
  const [options, setOptions] = useState<ProductOption[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!token || supplierId === null) {
      setOptions([])
      return
    }
    let active = true
    const timer = setTimeout(() => {
      setLoading(true)
      fetchProducts(token, {
        supplier_id: supplierId,
        search: input || undefined,
        page_size: 50,
      })
        .then((response) => {
          if (active) setOptions(response.items.map(toOption))
        })
        .catch(() => {
          if (active) setOptions([])
        })
        .finally(() => {
          if (active) setLoading(false)
        })
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [token, supplierId, input])

  const merged = useMemo(() => {
    if (value && !options.some((option) => option.id === value.id)) {
      return [value, ...options]
    }
    return options
  }, [options, value])

  return (
    <Autocomplete
      size="small"
      disabled={disabled || supplierId === null}
      options={merged}
      loading={loading}
      value={value}
      onChange={(_event, next) => onChange(next)}
      onInputChange={(_event, next, reason) => {
        if (reason === 'input') setInput(next)
        else if (reason === 'clear') setInput('')
      }}
      getOptionLabel={(option) => option.name}
      isOptionEqualToValue={(option, current) => option.id === current.id}
      noOptionsText={supplierId === null ? 'Elige un proveedor' : 'Sin productos'}
      renderInput={(params) => (
        <TextField {...params} label="Producto" placeholder="Buscar…" />
      )}
    />
  )
}

export interface OrderDialogProps {
  open: boolean
  // null = alta; una orden borrador = edición.
  order: PurchaseOrder | null
  onClose: () => void
  onSaved: () => void
}

export default function OrderDialog({
  open,
  order,
  onClose,
  onSaved,
}: OrderDialogProps) {
  const { token } = useAuth()
  const isEdit = order !== null

  const [supplierId, setSupplierId] = useState('')
  const [expectedDate, setExpectedDate] = useState('')
  const [lines, setLines] = useState<OrderLine[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !token) return
    let active = true
    setError(null)
    setSaving(false)
    fetchSuppliers(token)
      .then((response) => {
        if (active) setSuppliers(response)
      })
      .catch(() => {
        // El diálogo sigue usable aunque no carguen los proveedores.
      })

    if (order) {
      setSupplierId(String(order.supplier_id))
      setExpectedDate(
        order.expected_date ? String(order.expected_date).slice(0, 10) : '',
      )
      setLines([])
      setLoading(true)
      fetchPurchaseOrder(token, order.id)
        .then((detail) => {
          const ids = detail.items.map((item) => item.product_id)
          const namesPromise = ids.length
            ? fetchProducts(token, {
                ids: ids.join(','),
                is_active: undefined,
                page_size: 100,
              })
                .then((response) => {
                  const map = new Map<number, ProductOption>()
                  response.items.forEach((product) =>
                    map.set(product.id, toOption(product)),
                  )
                  return map
                })
                .catch(() => new Map<number, ProductOption>())
            : Promise.resolve(new Map<number, ProductOption>())
          return namesPromise.then((names) => {
            if (!active) return
            setLines(
              detail.items.map((item) => ({
                key: nextKey(),
                product: names.get(item.product_id) ?? {
                  id: item.product_id,
                  name: `Producto #${item.product_id}`,
                  is_active: false,
                },
                quantity: String(item.quantity),
                unitCost: String(item.unit_cost),
              })),
            )
          })
        })
        .catch((err: unknown) => {
          if (active)
            setError(
              err instanceof Error ? err.message : 'Error al cargar la orden',
            )
        })
        .finally(() => {
          if (active) setLoading(false)
        })
    } else {
      setSupplierId('')
      setExpectedDate('')
      setLines([createLine()])
      setLoading(false)
    }
    return () => {
      active = false
    }
  }, [open, order, token])

  const parsed = lines.map((line) => ({
    productId: line.product?.id ?? null,
    quantity: Number(line.quantity),
    unitCost: Number(line.unitCost),
  }))

  const productIds = parsed
    .map((item) => item.productId)
    .filter((id): id is number => id !== null)
  const hasDuplicates = new Set(productIds).size !== productIds.length

  const total = lines.reduce((sum, line) => {
    const quantity = Number(line.quantity)
    const unitCost = Number(line.unitCost)
    if (!Number.isFinite(quantity) || !Number.isFinite(unitCost)) return sum
    return sum + quantity * unitCost
  }, 0)

  const valid =
    supplierId !== '' &&
    lines.length > 0 &&
    !hasDuplicates &&
    parsed.every(
      (item) =>
        item.productId !== null &&
        Number.isInteger(item.quantity) &&
        item.quantity > 0 &&
        Number.isFinite(item.unitCost) &&
        item.unitCost >= 0,
    )

  const lineSubtotal = (line: OrderLine): number => {
    const quantity = Number(line.quantity)
    const unitCost = Number(line.unitCost)
    if (!Number.isFinite(quantity) || !Number.isFinite(unitCost)) return 0
    return quantity * unitCost
  }

  const updateLine = (key: number, patch: Partial<OrderLine>) => {
    setLines((prev) =>
      prev.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    )
  }

  const addLine = () => setLines((prev) => [...prev, createLine()])

  const removeLine = (key: number) =>
    setLines((prev) => prev.filter((line) => line.key !== key))

  const handleSupplierChange = (value: string) => {
    setSupplierId(value)
    // Los productos de la orden deben pertenecer al proveedor elegido.
    setLines(value ? [createLine()] : [])
  }

  const handleSave = async () => {
    if (!token || !valid || saving) return
    setSaving(true)
    setError(null)
    const items: PurchaseOrderItemIn[] = lines.map((line) => ({
      product_id: line.product!.id,
      quantity: Number(line.quantity),
      unit_cost: Number(line.unitCost),
    }))
    try {
      if (order) {
        await updatePurchaseOrder(token, order.id, {
          expected_date: expectedDate || undefined,
          items,
        })
      } else {
        await createPurchaseOrder(token, {
          supplier_id: Number(supplierId),
          expected_date: expectedDate || undefined,
          items,
        })
      }
      onSaved()
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'No se pudo guardar la orden')
      setSaving(false)
    }
  }

  const supplierName = (id: number): string => {
    const found = suppliers.find((item) => item.id === id)
    return found ? found.name : `Proveedor #${id}`
  }

  return (
    <Dialog
      open={open}
      onClose={saving ? undefined : onClose}
      fullWidth
      maxWidth="md"
    >
      <DialogTitle>
        {isEdit ? `Editar orden #${order?.id}` : 'Nueva orden de compra'}
      </DialogTitle>
      <DialogContent dividers>
        {loading ? (
          <Box sx={{ py: 6, display: 'flex', justifyContent: 'center' }}>
            <CircularProgress size={32} />
          </Box>
        ) : (
          <Stack spacing={3}>
            {error && <Alert severity="error">{error}</Alert>}

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <FormControl size="small" fullWidth disabled={isEdit}>
                <InputLabel id="order-supplier-label">Proveedor</InputLabel>
                <Select
                  labelId="order-supplier-label"
                  label="Proveedor"
                  value={supplierId}
                  onChange={(event) => handleSupplierChange(event.target.value)}
                >
                  <MenuItem value="" disabled>
                    Elige un proveedor
                  </MenuItem>
                  {suppliers.map((supplier) => (
                    <MenuItem key={supplier.id} value={String(supplier.id)}>
                      {supplier.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <TextField
                label="Fecha esperada"
                type="date"
                size="small"
                fullWidth
                value={expectedDate}
                onChange={(event) => setExpectedDate(event.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Stack>

            {isEdit && supplierId && (
              <Typography variant="body2" color="text.secondary">
                Proveedor: {supplierName(Number(supplierId))} (no editable)
              </Typography>
            )}

            <Stack spacing={1.5}>
              {lines.map((line) => (
                <Stack
                  key={line.key}
                  direction={{ xs: 'column', sm: 'row' }}
                  spacing={1.5}
                  sx={{ alignItems: { sm: 'center' } }}
                >
                  <Box sx={{ flex: 2, minWidth: 200 }}>
                    <ProductAutocomplete
                      token={token ?? ''}
                      supplierId={supplierId ? Number(supplierId) : null}
                      value={line.product}
                      disabled={saving}
                      onChange={(product) => updateLine(line.key, { product })}
                    />
                  </Box>
                  <TextField
                    label="Cantidad"
                    type="number"
                    size="small"
                    sx={{ width: { xs: '100%', sm: 110 } }}
                    value={line.quantity}
                    onChange={(event) =>
                      updateLine(line.key, { quantity: event.target.value })
                    }
                    slotProps={{ htmlInput: { min: 1, step: 1 } }}
                  />
                  <TextField
                    label="Costo unit."
                    type="number"
                    size="small"
                    sx={{ width: { xs: '100%', sm: 130 } }}
                    value={line.unitCost}
                    onChange={(event) =>
                      updateLine(line.key, { unitCost: event.target.value })
                    }
                    slotProps={{ htmlInput: { min: 0, step: 0.01 } }}
                  />
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 600, minWidth: 110, textAlign: 'right' }}
                  >
                    {formatMoney(lineSubtotal(line))}
                  </Typography>
                  <Button
                    size="small"
                    color="error"
                    onClick={() => removeLine(line.key)}
                    disabled={lines.length === 1 || saving}
                  >
                    Quitar
                  </Button>
                </Stack>
              ))}
            </Stack>

            <Box>
              <Button
                size="small"
                onClick={addLine}
                disabled={!supplierId || saving}
              >
                Añadir ítem
              </Button>
            </Box>

            {hasDuplicates && (
              <Alert severity="warning">
                Hay productos repetidos en los ítems.
              </Alert>
            )}

            <Divider />

            <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                Total
              </Typography>
              <Typography variant="body1" sx={{ fontWeight: 700 }}>
                {formatMoney(total)}
              </Typography>
            </Stack>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          Cancelar
        </Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={!valid || saving || loading}
        >
          {saving ? 'Guardando…' : 'Guardar'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
