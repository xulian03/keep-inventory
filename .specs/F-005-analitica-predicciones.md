# F-005 — Analítica y predicciones (unifica antiguas F-005 Analítica + F-006 Predicciones)

## Objetivo
Backend de analítica y predicciones en sales (:8003), admin-only (RBAC existente), usando
solo endpoints existentes de inventory (REST, JWT reenviado): KPIs con delta, tendencia
día/semana/mes, por categoría, top productos, resumen de compras y predicciones por
producto (regresión sklearn + media móvil). Sin cambios en inventory/auth ni seed.py; sin caché.

## Endpoints nuevos (routers/analytics.py y routers/predictions.py de sales)
1. GET /analytics/kpis (date_from, date_to; default últimos 30 días): {period, sales{total,
   transactions, avg_ticket, units, delta_pct{...}}, inventory{value, products_total,
   counts{agotado, bajo, disponible, exceso}}}. sales: SQL local del rango; delta =
   (act−ant)/ant·100 vs período anterior de igual largo (null si anterior sin ventas).
   inventory: loop GET /products?is_active=1 (page_size=100) → value = Σ stock·sale_price,
   counts por state, products_total. Regla de rangos (todos los endpoints con rango):
   extremo que falta → hoy / hoy−29; 422 si from > to.
2. GET /analytics/sales-trend (group_by=day|week|month [day], date_from, date_to,
   category): {group_by, from, to, points[{bucket, total, units, transactions}]}; SQL
   agrupa por día (category filtra sale_items); semana/mes se pliega en Python (lunes ISO
   / 'YYYY-MM'); solo buckets con ventas.
3. GET /analytics/sales-by-category (date_from, date_to): {items[{category, total, units}]}
   desc por total (default últimos 30 días).
4. GET /analytics/top-products (date_from, date_to, category, limit [10, máx 50]):
   {items[{product_id, product_name, category, units, total}]} desc por total, todo local
   (sale_items denormalizado; sin llamar a inventory).
5. GET /analytics/purchases-summary (date_from, date_to sobre received_at; default todas):
   {totals{orders_received, spend_received, counts_by_status}, by_month[{month, orders,
   spend}], by_supplier[{supplier_id, supplier_name, orders, spend}]}; fuente
   GET /purchase-orders (loop de páginas de 100) + GET /suppliers; spend = Σ order.total
   de órdenes recibidas.
6. GET /predictions (page, page_size [50, máx 100], category): {items, total, page,
   page_size}; por página: 1 llamada GET /products?page&category&is_active=1 (stock,
   min_threshold, state, nombre) + serie diaria local (120 días) de esos ids; item:
   {product_id, product_name, category, stock, min_threshold, state, method,
   daily_demand, trend, stockout_date, demand_30d, suggested_reorder}.

## Modelo (forecasting.py, funciones puras; ARCHITECTURE §8)
- Convención del repo: identificadores/campos EN INGLÉS; valores de enums en español.
- predict_demand(serie: list[int], stock, min_threshold, hoy) -> Forecast{daily_demand,
  trend, method, stockout_date, demand_30d, suggested_reorder}.
- Serie diaria de 120 días (ceros incluidos). ≥10 días con ventas: regresión y = m·d + b
  (d=0..n−1); daily_demand = media de proyección d=n..n+29 (mín 0); trend: |m|·30 ≤
  5%·media diaria → 'estable', si no signo(m) ('subiendo'/'bajando').
- <10 días: media móvil simple 30 días (ceros incluidos), trend 'estable'; method ∈
  {'regresion', 'media_movil'}.
- stockout_date = hoy + stock/daily_demand (null si daily_demand = 0); demand_30d =
  round(daily_demand·30); suggested_reorder = max(0, round(demand_30d + min_threshold − stock)).

## Archivos afectados
- Nuevos: services/sales/src/sales/{analytics.py, forecasting.py, routers/analytics.py,
  routers/predictions.py}; tests: test_forecasting.py, test_analytics.py,
  test_purchases_summary.py, test_predictions.py.
- Editar: inventory_client.py (get_products_page, get_all_purchase_orders, get_suppliers),
  main.py (registrar routers), tests/conftest.py (mock inventory: products paginado,
  órdenes, proveedores).
- Housekeeping: frontend/src/App.tsx (placeholders → F-006, F-007/F-008, F-009).

## Pasos atómicos
1. forecasting.py puro + test_forecasting.py (tendencia, fallback, fórmulas, bordes).
2. analytics.py (SQL local: kpis por rango, serie diaria, categoría, top) + tests.
3. /analytics/kpis (client.get_products_page + delta) + tests (default 30 días, 403).
4. /sales-trend + /sales-by-category + /top-products (solo SQL local) + tests (buckets).
5. /purchases-summary (client.get_all_purchase_orders + get_suppliers) + tests.
6. /predictions (página inventory + serie local + modelo) + tests (regresión vs fallback).
7. Housekeeping App.tsx + verificación completa (todos los comandos, tiempos <2 s).

## Criterios de aceptación
- pytest -q verde (services + scripts/tests); ruff check limpio; npm run build OK.
- Con BD sembrada: admin 200 / empleado 403 en los 6; kpis ~0.6 s y predictions ~0.12 s
  en régimen (2.ª llamada; la 1.ª tras arrancar paga cold-start del equipo: warm-up en
  AGENTS.md); method 'regresion' (≥10 días con ventas) / 'media_movil'.
- inventory y auth intactos (sus tests verdes sin cambios).

## Fuera de alcance
- Frontend (F-006 login, F-007 dashboard, F-008 decisión), caché, estacionalidad anual,
  KPIs de margen (sin costo por producto), cambios en modelos/seed.py, /auth/users.

## Comandos de verificación
- .venv\Scripts\ruff check services ; .venv\Scripts\pytest -q ; cd frontend ; npm run build
- .\start-all.ps1 + smoke con admin@tienda.com/admin123 (Bearer) a :8003: /analytics/kpis,
  /analytics/sales-trend?group_by=week, /analytics/purchases-summary, /predictions
  (Measure-Command, <2 s).
