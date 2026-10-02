# F-008 — Frontend admin: decisión (predicciones, órdenes, ventas, edición)

## Objetivo
Sustituir los 3 placeholders de /admin (Predicciones, Órdenes de compra, Ventas) por paneles
reales y añadir edición de umbrales y productos al tab Inventario existente. Sin backend nuevo.

## Contratos consumidos (sin cambios; apiFetch + Bearer)
- sales :8003 (admin): GET /predictions (page, page_size≤100, category) → {items[{product_id,
  product_name, category, stock, min_threshold, state, method, daily_demand, trend,
  stockout_date, demand_30d, suggested_reorder}], total, page, page_size}; GET /sales
  (category, date_from, date_to, page) → {items[{id, employee_id, created_at, total,
  items[{product_name, category, quantity, unit_price, line_total}]}], total, page, page_size}
  — los ítems de cada venta ya vienen en la lista (sin fetch extra).
- inventory :8002 (admin): PATCH /products/{id} {name?, sale_price?>0, market_price?>=0,
  is_active?}; PATCH /products/{id}/threshold {min_threshold?>=0, excess_threshold?};
  GET /suppliers; POST /purchase-orders {supplier_id, expected_date?, items[{product_id,
  quantity>0, unit_cost>=0}]} (201); GET /purchase-orders (status, supplier_id, date_from,
  date_to, page) → filas SIN ítems (con total); GET /purchase-orders/{id} → detalle con
  ítems; PATCH /purchase-orders/{id} (solo borrador; items? REEMPLAZA todos); DELETE
  /purchase-orders/{id} (solo borrador); POST .../send (solo borrador); POST .../cancel
  (solo enviada).
- Restricción del backend: los ítems deben ser productos del proveedor de la orden → el
  selector de producto filtra por supplier_id (GET /products?supplier_id=&search=&is_active=1).

## Decisiones
- Predicciones: tabla MUI read-only con filtro de categoría (Select de /categories, como
  F-007) + paginación server-side (TablePagination, 50/pág, total real); columnas producto,
  categoría, stock, umbral, estado (Chip colores §7), método, demanda/día, tendencia,
  agotamiento (stockout_date || "—"), demanda 30d, sugerido. Sin ordenación.
- Órdenes: filtros estado (borrador/enviada/recibida/cancelada) + proveedor (Select
  /suppliers); DataGrid paginado server-side (sortable=false); columnas id, proveedor,
  estado (Chip), creada, esperada, total $, n ítems, acciones.
- Diálogo Nueva/Editar orden (mismo diálogo; editar solo borradores, precargado del
  detalle): Select proveedor (ítems deshabilitados hasta elegir), fecha esperada opcional,
  ítems dinámicos: Autocomplete de productos del proveedor + cantidad + costo unitario,
  total en vivo; validación client (cantidad>0, costo>=0, sin duplicados).
- Acciones por fila según estado: borrador → editar, enviar, eliminar; enviada → cancelar,
  ver; recibida/cancelada → ver. Enviar/cancelar/eliminar con confirmación (Dialog). "Ver"
  abre diálogo con detalle (GET /{id}) e ítems. Tras cada acción: refresco de lista.
- Inventario (F-007): columna de acciones → diálogo umbral (min, exceso) y diálogo producto
  (nombre, precio venta, precio mercado, activo Switch); éxito → Snackbar + refresco de
  tabla conservando filtros y página.
- Ventas: filtros categoría (Select) + rango libre con 2 TextField date (from>to → Alert
  sin llamar); tabla MUI paginada server-side; columnas id, fecha (ISO corta), vendedor
  (employee_id), total $, unidades; expansión de fila (Collapse) con ítems.
- Errores 403/409/422 → Snackbar con detail del backend; carga con CircularProgress como
  F-007; fechas ISO-8601; UI en español, valores de enum tal cual.

## Archivos afectados
- Nuevos: frontend/src/admin/{PrediccionesPanel.tsx, OrdenesPanel.tsx, VentasPanel.tsx,
  OrderDialog.tsx}.
- Editar: frontend/src/admin/api.ts (tipos + fetchers: predicciones, órdenes CRUD+send+
  cancel, ventas, suppliers, patchProduct, patchThreshold), admin/InventarioPanel.tsx
  (columna acciones + 2 diálogos + refresco), pages/Admin.tsx (3 tabs reales).
- Sin tocar: backend, AuthContext, api/client.ts, theme.ts, AppLayout, Login, Empleado.

## Pasos atómicos
1. admin/api.ts: tipos y fetchers de los contratos nuevos (+GET /suppliers).
2. PrediccionesPanel.tsx: tabla + filtro de categoría + paginación server-side.
3. OrdenesPanel.tsx: filtros + DataGrid paginado + chips + acciones por estado + ver
   detalle + confirmaciones + refresco tras acción.
4. OrderDialog.tsx + wiring en OrdenesPanel: alta y edición de borrador con ítems por
   proveedor, total en vivo y validaciones.
5. InventarioPanel.tsx: columna de acciones + diálogo umbral + diálogo producto + Snackbar
   + refresco conservando filtros/página.
6. VentasPanel.tsx: filtros + tabla paginada + expansión de ítems.
7. Admin.tsx: sustituir los 3 placeholders; verificación final (lint, build, smoke manual).

## Criterios de aceptación
- cd frontend: npm run lint limpio; npm run build OK.
- Smoke con .\start-all.ps1 + semilla (tras warm-up) como admin@tienda.com/admin123:
  - Predicciones: filas con método, agotamiento y sugerido reales; página y categoría
    cambian y recalculan el total.
  - Órdenes: crear borrador con ítems del proveedor → aparece; editar cambia ítems/fecha;
    enviar → enviada; cancelar → cancelada; eliminar quita borradores; acciones visibles
    solo según estado; confirmaciones presentes.
  - Inventario: editar umbral cambia el semáforo del producto tras refrescar; editar
    producto persiste nombre/precios/activo.
  - Ventas: categoría/fechas acotan resultados; expansión muestra ítems con subtotales;
    paginación server-side funciona.
- Backend intacto: ruff + pytest verdes (sin cambios esperados).

## Fuera de alcance
- Recibir órdenes (F-009), generar órdenes desde predicciones, gráficas en Ventas, filtros
  por producto/vendedor en Ventas, ordenación server-side, exportar CSV, tests de frontend,
  responsive móvil, cambios de backend, F-010.

## Comandos de verificación
- cd frontend ; npm run lint ; npm run build
- .\start-all.ps1 ; http://localhost:5173 (admin@tienda.com/admin123; 1.ª carga lenta)
- Opcional: .venv\Scripts\ruff check services ; .venv\Scripts\pytest -q
