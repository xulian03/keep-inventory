import { apiFetch, INVENTORY_URL } from './client'

export type InventoryState = 'agotado' | 'bajo' | 'disponible' | 'exceso'

export type OrderStatus = 'borrador' | 'enviada' | 'recibida' | 'cancelada'

// Colores del semáforo §7 (agotado/bajo/disponible/exceso).
export const STATE_COLORS: Record<InventoryState, string> = {
  agotado: '#EF4444',
  bajo: '#F59E0B',
  disponible: '#10B981',
  exceso: '#3B82F6',
}

// --- inventory :8002 (autenticado) ---

export interface Product {
  id: number
  name: string
  brand: string
  category: string
  subcategory: string
  sale_price: number
  stock: number
  min_threshold: number
  excess_threshold: number
  state: InventoryState
  is_active: boolean
}

export interface ProductsResponse {
  items: Product[]
  total: number
  page: number
  page_size: number
}

export interface ProductsParams {
  search?: string
  ids?: string
  category?: string
  state?: InventoryState
  supplier_id?: number
  is_active?: number
  page?: number
  page_size?: number
}

export interface CategoriesResponse {
  categories: string[]
  subcategories: string[]
}

type QueryValue = string | number | boolean | undefined

export function withQuery(base: string, params: Record<string, QueryValue>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `${base}?${query}` : base
}

export function fetchProducts(
  token: string,
  params: ProductsParams = {},
): Promise<ProductsResponse> {
  return apiFetch<ProductsResponse>(
    withQuery(`${INVENTORY_URL}/products`, {
      is_active: 1,
      page: 1,
      page_size: 50,
      ...params,
    }),
    { token },
  )
}

export function fetchCategories(token: string): Promise<CategoriesResponse> {
  return apiFetch<CategoriesResponse>(`${INVENTORY_URL}/categories`, { token })
}

// --- formato (es-ES, moneda "$" genérico) ---

const moneyFmt = new Intl.NumberFormat('es-ES', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const pctFmt = new Intl.NumberFormat('es-ES', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

export function formatMoney(value: number): string {
  return `$${moneyFmt.format(value)}`
}

export function formatPct(delta: number | null): string {
  if (delta === null) return '—'
  if (delta === 0) return `${pctFmt.format(0)} %`
  const arrow = delta > 0 ? '▲' : '▼'
  return `${arrow} ${pctFmt.format(Math.abs(delta))} %`
}
