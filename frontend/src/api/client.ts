export const AUTH_URL = import.meta.env.VITE_AUTH_URL ?? 'http://localhost:8001'
export const INVENTORY_URL = import.meta.env.VITE_INVENTORY_URL ?? 'http://localhost:8002'
export const SALES_URL = import.meta.env.VITE_SALES_URL ?? 'http://localhost:8003'

export interface ApiFetchOptions {
  method?: string
  body?: unknown
  token?: string
}

export async function apiFetch<T>(url: string, opts?: ApiFetchOptions): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (opts?.token) headers.Authorization = `Bearer ${opts.token}`

  const res = await fetch(url, {
    method: opts?.method ?? 'GET',
    headers,
    body: opts?.body !== undefined ? JSON.stringify(opts.body) : undefined,
  })

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const data = (await res.json()) as { detail?: unknown }
      if (typeof data.detail === 'string') detail = data.detail
      else if (data.detail !== undefined) detail = JSON.stringify(data.detail)
    } catch {
      // respuesta sin cuerpo JSON: se usa el texto por defecto
    }
    throw new Error(detail)
  }

  return (await res.json()) as T
}
