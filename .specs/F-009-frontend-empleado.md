# F-009 — Frontend empleado

## Objetivo
Página /empleado funcional reemplazando los 3 placeholders: registrar venta (POS con buscador
y carrito, descuenta stock en vivo), recibir mercancía (órdenes de compra) y catálogo simple.
Estilo Lightdash coherente con el resto (AppLayout, tarjetas blancas, theme.ts).

## Endpoints que consume (ya implementados, no tocar backend)
- GET /products (inventory): search, category, state, page, page_size; ProductOut con
  sale_price, stock, state, is_active, min_threshold.
- POST /sales (sales): body {items:[{product_id, quantity}]}; recalcula precios server-side;
  201 devuelve venta (líneas, total) + stock resultante; 409/422 si no alcanza stock.
- GET /purchase-orders (inventory): filtro status + paginación; GET /purchase-orders/{id}
  con items; POST /purchase-orders/{id}/receive (solo status "enviada", rol empleado/admin).

## Archivos
- Nuevos: frontend/src/api/shared.ts; frontend/src/empleado/{api.ts, RegistrarVentaPanel.tsx,
  RecibirMercanciaPanel.tsx, CatalogoPanel.tsx} (diálogo de recepción dentro de RecibirMercanciaPanel).
- Modificados: frontend/src/admin/api.ts y admin/{InventarioPanel,ResumenPanel}.tsx (imports,
  paso 1); frontend/src/pages/Empleado.tsx (conectar pestañas).

## Pasos atómicos
1. Extraer compartidos: mover a frontend/src/api/shared.ts los tipos de catálogo (Product,
   ProductsResponse, filtros), helpers (withQuery, fetchProducts, fetchCategories,
   formatMoney/formatPct) y STATE_COLORS (hoy duplicado en InventarioPanel y ResumenPanel).
   admin/ pasa a importar de ahí; sin cambios de comportamiento.
2. empleado/api.ts: tipos PurchaseOrder, PurchaseOrderDetail y OrderStatus; funciones
   fetchPurchaseOrders(status, page, page_size), fetchPurchaseOrder(id), receivePurchaseOrder(id),
   createSale(items) sobre apiFetch (client.ts, sin cambios).
3. RegistrarVentaPanel (POS): buscador con debounce (search, page_size ~10) con resultados
   clickeables que agregan al carrito; carrito con cantidades editables (entero >0 y <= stock;
   inactivos no seleccionables), eliminar línea, total en vivo con sale_price; botón "Cobrar" →
   createSale; éxito: Snackbar/Alert con ticket (id de venta, líneas, total) y stock resultante,
   vaciar carrito y refrescar resultados del buscador; 409/422/502 mostrados con su detail;
   deshabilitar envío mientras carga o con carrito vacío.
4. RecibirMercanciaPanel: DataGrid server-side de fetchPurchaseOrders con filtro de estado
   (default "enviada"), chip coloreado por OrderStatus; columnas: id, proveedor, nº artículos,
   total, fecha esperada, estado; acción "Recibir" solo en "enviada" → diálogo con líneas
   (producto, cantidad, costo) → confirmar receivePurchaseOrder; éxito: toast + refresco;
   409 mostrado.
5. CatalogoPanel: DataGrid con búsqueda (debounce), filtro de categoría (fetchCategories) y
   estado; columnas: nombre, marca, categoría, precio (formatMoney), stock, umbral y estado con
   badge STATE_COLORS; paginación server-side 50/pág.
6. Empleado.tsx: reemplazar los 3 Placeholder por los paneles nuevos (mismas pestañas y títulos).

## Criterios de aceptación
- Login empleado@tienda.com / empleado123: una venta con 2+ productos descuenta stock (visible
  en Catálogo) y muestra ticket con total y stock resultante; vender más que el stock muestra
  el error sin romper la app.
- Recibir una orden enviada suma stock y la orden pasa a "recibida"; en otros estados no
  aparece "Recibir".
- Catálogo pagina y filtra server-side; búsqueda con debounce.
- Admin funciona igual que antes (solo imports movidos).
- npm run lint y npm run build limpios en frontend/.

## Fuera de alcance
- Historial/"Mis ventas" (4ª pestaña), editar productos/umbrales, crear/enviar órdenes de
  compra (F-008), paneles admin, imágenes de producto, i18n, ajuste móvil fino.

## Comandos de verificación
- Desde frontend/ (PowerShell): npm run lint ; npm run build
- Demo manual (seed + .\start-all.ps1): login empleado → registrar venta → catálogo →
  recibir mercancía. Salud: Invoke-WebRequest http://localhost:8002/health
