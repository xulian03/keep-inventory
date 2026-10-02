# F-007 — Frontend admin: dashboard (paneles Resumen e Inventario)

## Objetivo
Paneles reales para las pestañas Resumen e Inventario de /admin: KPIs con delta %, 4 gráficas
interactivas (filtros de fecha y categoría), chips de semáforo clicables y DataGrid de inventario
con paginación server-side. Sin cambios de backend.

## Contratos consumidos (F-004/F-005, sin cambios; apiFetch + Bearer)
- sales :8003 (admin): GET /analytics/kpis (date_from/date_to) → {period, sales{total,
  transactions, avg_ticket, units, delta_pct{...}}, inventory{value, products_total,
  counts{agotado,bajo,disponible,exceso}}}; GET /analytics/sales-trend (group_by, fechas,
  category) → {points[{bucket,total,units,transactions}]}; GET /analytics/sales-by-category
  (fechas) → {items[{category,total,units}]}; GET /analytics/top-products (fechas, category,
  limit=10) → {items[{product_id,product_name,category,units,total}]};
  GET /analytics/purchases-summary (fechas) → {totals{...}, by_month[{month,orders,spend}]}.
- inventory :8002 (autenticado): GET /products (search, category, state, is_active=1, page,
  page_size) → {items,total,page,page_size}; ítem: id, name, brand, category, subcategory,
  sale_price, stock, min_threshold, excess_threshold + state. GET /categories →
  {categories, subcategories}.
- Límite honesto de la API: kpis, by-category y purchases-summary NO aceptan category → el
  filtro de categoría solo afecta a tendencia y top productos; no simularlo en el resto.

## Decisiones (marcadas para veto)
- Fechas: presets 7/30/90 días (from = hoy−N+1, to = hoy, ISO local) + rango libre con 2
  TextField type="date"; from>to → Alert sin llamar; 422 del backend → Alert.
- Resumen: 4 KPIs de venta (total, transacciones, ticket promedio, unidades) con chip de
  delta % (▲/▼ verde/rojo; null → "—") + fila de inventario: valor $, productos activos y
  4 chips de conteo por estado con colores §7, clicables → pestaña Inventario con ese state.
- Gráficas (Recharts, chartColors): tendencia = área con degradado + ToggleButton
  día/semana/mes; por categoría = barras verticales redondeadas; top 10 = barras
  horizontales; compras = barras de spend por mes (by_month).
- Inventario: DataGrid (@mui/x-data-grid) siempre is_active=1; filtros search (TextField),
  categoría y estado (Select, state ∈ agotado/bajo/disponible/exceso); paginación
  server-side (page_size 50, rowCount=total, página desde /products); columnas id, name,
  category, brand, stock, min_threshold, sale_price, state (Chip coloreado §7);
  sortable=false (el backend no soporta orden).
- AppLayout acepta value/onIndexChange opcionales; Admin controla la pestaña activa
  (Empleado queda igual, sin cambios).

## Archivos afectados
- Nuevos: frontend/src/admin/{api.ts (tipos + funciones fetch*(token, params) sobre
  apiFetch + formatMoney/formatPct con Intl, "$"), KpiCard.tsx, FilterBar.tsx,
  ResumenPanel.tsx, InventarioPanel.tsx}.
- Editar: frontend/src/pages/Admin.tsx (pestañas reales + pestaña activa + state inicial),
  frontend/src/components/AppLayout.tsx (props controladas opcionales).
- Sin tocar: backend, AuthContext, api/client.ts, theme.ts, Empleado.

## Pasos atómicos
1. admin/api.ts: tipos de los 6 contratos + funciones de fetch + formatMoney/formatPct.
2. KpiCard.tsx (número grande + etiqueta + chip delta) + FilterBar.tsx (presets, rango
   libre, Select de categoría desde /categories) — componentes puros.
3. ResumenPanel.tsx (parte 1): filtros → KPIs + fila de inventario con chips clicables
   (prop onStateClick) + CircularProgress por tarjeta + Alert en error.
4. ResumenPanel.tsx (parte 2): 4 gráficas (área tendencia con group_by, barras categoría,
   top 10 horizontal, compras por mes), re-render al cambiar filtros.
5. InventarioPanel.tsx: DataGrid + filtros + paginación server-state; AppLayout
   value/onIndexChange + wiring en Admin.tsx (chip → pestaña Inventario con state aplicado).
6. Verificación completa: lint, build y smoke manual con warm-up (AGENTS.md: la 1.ª carga
   del dashboard paga cold-start del equipo).

## Criterios de aceptación
- cd frontend: npm run lint limpio; npm run build OK.
- Con .\start-all.ps1 + semilla (tras warm-up): Resumen muestra 4 KPIs con delta vs
  período anterior, valor de inventario y chips con conteos reales; cambiar fechas y
  categoría refresca lo afectado (<2 s en régimen); tendencia cambia con día/semana/mes;
  clic en chip "bajo" → pestaña Inventario ya filtrada; DataGrid pagina (50/página,
  rowCount real), búsqueda y filtros funcionan, chips de estado con colores §7.
- Backend intacto: ruff + pytest verdes (sin cambios esperados).

## Fuera de alcance
- Pestañas Predicciones/Órdenes de compra/Ventas (F-008+), editar productos/umbrales,
  compras por proveedor en UI, exportar CSV, ordenación server-side, tests de frontend
  (no hay runner), responsive móvil.

## Comandos de verificación
- cd frontend ; npm run lint ; npm run build
- .\start-all.ps1 ; http://localhost:5173 con admin@tienda.com/admin123 (escenario de
  arriba; la 1.ª carga es lenta por warm-up).
- Opcional: .venv\Scripts\ruff check services ; .venv\Scripts\pytest -q
