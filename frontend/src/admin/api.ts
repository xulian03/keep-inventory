import { apiFetch, INVENTORY_URL, SALES_URL } from '../api/client'

export type InventoryState = 'agotado' | 'bajo' | 'disponible' | 'exceso'
export type OrderStatus = 'borrador' | 'enviada' | 'recibida' | 'cancelada'
export type TrendGroupBy = 'day' | 'week' | 'month'

export interface DateRangeParams {
  date_from?: string
  date_to?: string
}

// --- sales :8003 (admin) ---

export interface KpisResponse {
  period: { from: string; to: string }
  sales: {
    total: number
    transactions: number
    avg_ticket: number
    units: number
    delta_pct: {
      total: number | null
      transactions: number | null
      avg_ticket: number | null
      units: number | null
    }
  }
  inventory: {
    value: number
    products_total: number
    counts: Record<InventoryState, number>
  }
}

export interface TrendPoint {
  bucket: string
  total: number
  units: number
  transactions: number
}

export interface SalesTrendResponse {
  group_by: TrendGroupBy
  from: string
  to: string
  points: TrendPoint[]
}

export interface SalesTrendParams extends DateRangeParams {
  group_by?: TrendGroupBy
  category?: string
}

export interface CategorySalesItem {
  category: string
  total: number
  units: number
}

export interface SalesByCategoryResponse {
  items: CategorySalesItem[]
}

export interface TopProductItem {
  product_id: number
  product_name: string
  category: string
  units: number
  total: number
}

export interface TopProductsResponse {
  items: TopProductItem[]
}

export interface TopProductsParams extends DateRangeParams {
  category?: string
  limit?: number
}

export interface PurchasesSummaryResponse {
  totals: {
    orders_received: number
    spend_received: number
    counts_by_status: Record<OrderStatus, number>
  }
  by_month: { month: string; orders: number; spend: number }[]
  by_supplier: {
    supplier_id: number
    supplier_name: string | null
    orders: number
    spend: number
  }[]
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
}

export interface ProductsResponse {
  items: Product[]
  total: number
  page: number
  page_size: number
}

export interface ProductsParams {
  search?: string
  category?: string
  state?: InventoryState
  is_active?: number
  page?: number
  page_size?: number
}

export interface CategoriesResponse {
  categories: string[]
  subcategories: string[]
}

type QueryValue = string | number | boolean | undefined

function withQuery(base: string, params: Record<string, QueryValue>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `${base}?${query}` : base
}

export function fetchKpis(
  token: string,
  params: DateRangeParams = {},
): Promise<KpisResponse> {
  return apiFetch<KpisResponse>(
    withQuery(`${SALES_URL}/analytics/kpis`, { ...params }),
    { token },
  )
}

export function fetchSalesTrend(
  token: string,
  params: SalesTrendParams = {},
): Promise<SalesTrendResponse> {
  return apiFetch<SalesTrendResponse>(
    withQuery(`${SALES_URL}/analytics/sales-trend`, { ...params }),
    { token },
  )
}

export function fetchSalesByCategory(
  token: string,
  params: DateRangeParams = {},
): Promise<SalesByCategoryResponse> {
  return apiFetch<SalesByCategoryResponse>(
    withQuery(`${SALES_URL}/analytics/sales-by-category`, { ...params }),
    { token },
  )
}

export function fetchTopProducts(
  token: string,
  params: TopProductsParams = {},
): Promise<TopProductsResponse> {
  return apiFetch<TopProductsResponse>(
    withQuery(`${SALES_URL}/analytics/top-products`, {
      limit: 10,
      ...params,
    }),
    { token },
  )
}

export function fetchPurchasesSummary(
  token: string,
  params: DateRangeParams = {},
): Promise<PurchasesSummaryResponse> {
  return apiFetch<PurchasesSummaryResponse>(
    withQuery(`${SALES_URL}/analytics/purchases-summary`, { ...params }),
    { token },
  )
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
