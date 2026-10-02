import { apiFetch, INVENTORY_URL, SALES_URL } from '../api/client'
import { withQuery, type OrderStatus } from '../api/shared'

export type { OrderStatus }

// --- inventory :8002 (órdenes de compra) ---

export interface PurchaseOrderItem {
  id: number
  product_id: number
  quantity: number
  unit_cost: number
  total: number
}

export interface PurchaseOrder {
  id: number
  supplier_id: number
  status: OrderStatus
  expected_date: string
  created_at: string
  received_at: string | null
  total: number
  item_count: number
}

export interface PurchaseOrderDetail extends PurchaseOrder {
  items: PurchaseOrderItem[]
}

export interface PurchaseOrdersResponse {
  items: PurchaseOrder[]
  total: number
  page: number
  page_size: number
}

export function fetchPurchaseOrders(
  token: string,
  status: OrderStatus,
  page = 1,
  page_size = 50,
): Promise<PurchaseOrdersResponse> {
  return apiFetch<PurchaseOrdersResponse>(
    withQuery(`${INVENTORY_URL}/purchase-orders`, { status, page, page_size }),
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

export function receivePurchaseOrder(
  token: string,
  id: number,
): Promise<PurchaseOrderDetail> {
  return apiFetch<PurchaseOrderDetail>(
    `${INVENTORY_URL}/purchase-orders/${id}/receive`,
    { method: 'POST', token },
  )
}

// --- sales :8003 (registro de venta) ---

export interface SaleItemIn {
  product_id: number
  quantity: number
}

export interface SaleItem {
  id: number
  product_id: number
  product_name: string
  category: string
  quantity: number
  unit_price: number
  line_total: number
}

export interface Sale {
  id: number
  employee_id: number
  total: number
  created_at: string
  items: SaleItem[]
}

export interface SaleStock {
  product_id: number
  stock: number
}

export interface SaleCreatedResponse {
  venta: Sale
  stock: SaleStock[]
}

export function createSale(
  token: string,
  items: SaleItemIn[],
): Promise<SaleCreatedResponse> {
  return apiFetch<SaleCreatedResponse>(`${SALES_URL}/sales`, {
    method: 'POST',
    body: { items },
    token,
  })
}
