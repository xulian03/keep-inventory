import { apiFetch, INVENTORY_URL, SALES_URL } from '../api/client'
import {
  withQuery,
  type InventoryState,
  type OrderStatus,
  type Product,
} from '../api/shared'
import type {
  PurchaseOrderDetail,
  PurchaseOrdersResponse,
  Sale,
} from '../empleado/api'

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

// --- sales :8003 (admin): predicciones de demanda ---

export type PredictionMethod = 'regresion' | 'media_movil'
export type PredictionTrend = 'estable' | 'subiendo' | 'bajando'

export interface Prediction {
  product_id: number
  product_name: string
  category: string
  stock: number
  min_threshold: number
  state: InventoryState
  method: PredictionMethod
  daily_demand: number
  trend: PredictionTrend
  stockout_date: string | null
  demand_30d: number
  suggested_reorder: number
}

export interface PredictionsResponse {
  items: Prediction[]
  total: number
  page: number
  page_size: number
}

export interface PredictionsParams {
  page?: number
  page_size?: number
  category?: string
}

export function fetchPredictions(
  token: string,
  params: PredictionsParams = {},
): Promise<PredictionsResponse> {
  return apiFetch<PredictionsResponse>(
    withQuery(`${SALES_URL}/predictions`, {
      page: 1,
      page_size: 50,
      ...params,
    }),
    { token },
  )
}

// --- sales :8003 (admin): ventas ---

export interface SalesResponse {
  items: Sale[]
  total: number
  page: number
  page_size: number
}

export interface SalesParams extends DateRangeParams {
  category?: string
  page?: number
  page_size?: number
}

export function fetchSales(
  token: string,
  params: SalesParams = {},
): Promise<SalesResponse> {
  return apiFetch<SalesResponse>(
    withQuery(`${SALES_URL}/sales`, {
      page: 1,
      page_size: 50,
      ...params,
    }),
    { token },
  )
}

// --- inventory :8002 (admin): proveedores, productos y órdenes ---

export interface Supplier {
  id: number
  name: string
  contact_email: string
  lead_time_days: number
}

export function fetchSuppliers(token: string): Promise<Supplier[]> {
  return apiFetch<Supplier[]>(`${INVENTORY_URL}/suppliers`, { token })
}

export interface AdminProduct extends Product {
  type: string
  market_price: number
  rating: number | null
  supplier_id: number | null
  created_at: string
}

export interface ProductPatch {
  name?: string
  sale_price?: number
  market_price?: number
  is_active?: boolean
}

export interface ThresholdPatch {
  min_threshold?: number
  excess_threshold?: number
}

export function patchProduct(
  token: string,
  id: number,
  payload: ProductPatch,
): Promise<AdminProduct> {
  return apiFetch<AdminProduct>(`${INVENTORY_URL}/products/${id}`, {
    method: 'PATCH',
    body: payload,
    token,
  })
}

export function patchThreshold(
  token: string,
  id: number,
  payload: ThresholdPatch,
): Promise<AdminProduct> {
  return apiFetch<AdminProduct>(
    `${INVENTORY_URL}/products/${id}/threshold`,
    { method: 'PATCH', body: payload, token },
  )
}

export interface PurchaseOrderItemIn {
  product_id: number
  quantity: number
  unit_cost: number
}

export interface PurchaseOrderCreate {
  supplier_id: number
  expected_date?: string
  items: PurchaseOrderItemIn[]
}

export interface PurchaseOrderUpdate {
  expected_date?: string
  items?: PurchaseOrderItemIn[]
}

export interface PurchaseOrdersParams extends DateRangeParams {
  status?: OrderStatus
  supplier_id?: number
  page?: number
  page_size?: number
}

export function fetchPurchaseOrders(
  token: string,
  params: PurchaseOrdersParams = {},
): Promise<PurchaseOrdersResponse> {
  return apiFetch<PurchaseOrdersResponse>(
    withQuery(`${INVENTORY_URL}/purchase-orders`, {
      page: 1,
      page_size: 50,
      ...params,
    }),
    { token },
  )
}

export function fetchPurchaseOrder(
  token: string,
  id: number,
): Promise<PurchaseOrderDetail> {
  return apiFetch<PurchaseOrderDetail>(
    `${INVENTORY_URL}/purchase-orders/${id}`,
    { token },
  )
}

export function createPurchaseOrder(
  token: string,
  payload: PurchaseOrderCreate,
): Promise<PurchaseOrderDetail> {
  return apiFetch<PurchaseOrderDetail>(`${INVENTORY_URL}/purchase-orders`, {
    method: 'POST',
    body: payload,
    token,
  })
}

export function updatePurchaseOrder(
  token: string,
  id: number,
  payload: PurchaseOrderUpdate,
): Promise<PurchaseOrderDetail> {
  return apiFetch<PurchaseOrderDetail>(
    `${INVENTORY_URL}/purchase-orders/${id}`,
    { method: 'PATCH', body: payload, token },
  )
}

export async function deletePurchaseOrder(
  token: string,
  id: number,
): Promise<void> {
  try {
    await apiFetch<unknown>(`${INVENTORY_URL}/purchase-orders/${id}`, {
      method: 'DELETE',
      token,
    })
  } catch (error) {
    // El backend responde 204 sin cuerpo y apiFetch lo intenta parsear como JSON.
    if (error instanceof SyntaxError) return
    throw error
  }
}

export function sendPurchaseOrder(
  token: string,
  id: number,
): Promise<PurchaseOrderDetail> {
  return apiFetch<PurchaseOrderDetail>(
    `${INVENTORY_URL}/purchase-orders/${id}/send`,
    { method: 'POST', token },
  )
}

export function cancelPurchaseOrder(
  token: string,
  id: number,
): Promise<PurchaseOrderDetail> {
  return apiFetch<PurchaseOrderDetail>(
    `${INVENTORY_URL}/purchase-orders/${id}/cancel`,
    { method: 'POST', token },
  )
}
