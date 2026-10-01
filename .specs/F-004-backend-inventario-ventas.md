# Spec F-004 — Backend unificado: inventario (catálogo, stock, compras) y ventas

## Objetivo
Routers de negocio de inventory (:8002) y sales (:8003) sobre los modelos existentes de F-002 (§4.2/§4.3, sin cambios) y la RBAC de F-003. Fusiona las antiguas F-004/F-005/F-006. Sin tablas nuevas ni cambios en seed.py. El state de stock no se almacena: se calcula (§7).

## Decisiones consultadas (2026-10-01)
- Descuento por LOTE atómico: todo o nada; 409 si algún ítem no alcanza, sin descontar nada.
- PATCH /products/{id} (admin, parcial): name (no vacío), sale_price (>0), market_price (≥0), is_active. GET /products: filtro is_active (default: todos); ids= ignora paginación (devuelve todas las coincidencias).
- PATCH /purchase-orders/{id}: reemplazo completo de items + expected_date, solo borrador. DELETE /purchase-orders/{id}: 204 solo borrador (409 si no).
- Venta simple: sin cliente, método de pago ni devoluciones; + GET /sales/{id}.
- Defaults: page_size 50 (máx 100) en products/movements/purchase-orders/sales/alerts con respuesta {items,total,page,page_size}; movimiento manual reason ∈ {compra, ajuste} y 409 si stock resultante <0; employee_id desde el JWT; ítems duplicados → 422; products por id asc y resto por fecha desc; totales calculados (Σ qty×unit_cost, Σ qty×unit_price).

## Inventory :8002 (JWT requerido; roles según §5.2)
- GET /products (filtros §5.2 + is_active; state calculado por ítem) · GET /products/{id} (+supplier_name) · PATCH /products/{id} y PATCH /products/{id}/threshold (admin) · GET /categories · GET /suppliers · GET /alerts (agotado|bajo, stock asc, paginado).
- GET /movements (filtros product_id, movement_type, reason, date_from, date_to) · POST /movements (empleado, admin): {product_id, movement_type, quantity>0, reason, reference?} → actualiza stock; 409 si el stock resultante <0.
- POST /purchase-orders (admin): {supplier_id, expected_date?, items[{product_id, quantity>0, unit_cost≥0}]} → borrador (422 si producto/proveedor no existe) · GET /purchase-orders (filtros status, supplier_id, date_from, date_to; +total e item_count) · GET /purchase-orders/{id} (con items) · PATCH (reemplaza items completos; solo borrador) · DELETE (solo borrador).
- POST /purchase-orders/{id}/send (admin): borrador→enviada · /cancel (admin): enviada→cancelada sin tocar stock · /receive (empleado, admin): enviada→recibida, received_at, por ítem stock+=quantity y movimiento entrada reason=compra reference=orden. Estado inválido → 409.
- POST /internal/movements/salida (JWT reenviado): {reference, items[{product_id, quantity>0}]} en UNA transacción: valida stock de todos, descuenta todos y crea un movimiento (salida, reason=venta, reference) por ítem; 409 sin descontar nada si falta stock o no existe un producto; 200 {items:[{product_id, stock}]}.

## Sales :8003 (JWT requerido)
- POST /sales (empleado, admin): {items[{product_id, quantity>0}]}, sin duplicados (422). Flujo: 1) GET {INVENTORY_URL}/products?ids=... reenviando JWT → valida existencia, is_active y stock (404/422); 2) POST /internal/movements/salida con reference="venta:<uuid>" (JWT reenviado) → 200 o 409 (no registra nada); 3) guarda sale (employee_id=JWT sub, total=Σ qty×unit_price) + sale_items denormalizados; 4) 201 {venta, stock resultante}. Si inventario no responde → 502 sin registrar; si el guardado local falla tras descontar → compensa con POST /movements (entrada, reason=ajuste) y responde 502.
- GET /sales (filtros product_id, category, employee_id, date_from, date_to; ítems embebidos) · GET /sales/{id} (detalle con ítems, 404 si no existe).

## Archivos afectados
- services/inventory/src/inventory/: schemas.py (nuevo), state.py (nuevo), routers/ (nuevo: catalog.py, movements.py, purchase_orders.py, internal.py), main.py.
- services/sales/src/sales/: schemas.py (nuevo), inventory_client.py (nuevo, httpx), routers/sales.py (nuevo), main.py.
- services/inventory/tests/ y services/sales/tests/ (tests por paso) · frontend/src/App.tsx (placeholders F-009→F-007, F-010/F-011→F-008/F-009, F-012→F-010).

## Pasos atómicos (delegables uno a uno)
1. Inventory: schemas + state.py + GET /products (+filtros, ids batch sin paginar) + GET /products/{id} + GET /categories + tests.
2. Inventory: PATCH /products/{id} + PATCH threshold + GET /suppliers + GET /alerts + tests.
3. Inventory: GET /movements + POST /movements + tests.
4. Inventory: CRUD de purchase-orders (POST/GET/GET{id}/PATCH/DELETE) + tests.
5. Inventory: /send + /receive + /cancel (receive suma stock y crea movimientos) + tests.
6. Inventory: POST /internal/movements/salida atómico + tests (200, 409 sin cambios, 401).
7. Sales: schemas + inventory_client + POST /sales (flujo completo + compensación) + tests.
8. Sales: GET /sales (filtros, ítems embebidos) + GET /sales/{id} + tests.
9. App.tsx: renumerar placeholders; verificación final (comandos de abajo).

## Criterios de aceptación
- Endpoints y roles según §5.2/§5.3 (ya actualizadas); 401/403/404/409/422/502 bien usados.
- Venta con ítem sin stock → 409, nada descontado ni registrado; el ledger cuadra (stock == entradas−salidas) tras ventas, recepciones y movimientos manuales.
- Recibir una orden enviada suma stock y crea movimientos entrada reason=compra.
- Tests verdes (services + scripts/tests), ruff limpio, los 3 servicios arrancan.

## Fuera de alcance
- /analytics/* y /predictions (F-005/F-006), frontend de negocio, GET/POST /auth/users, cambios a modelos o seed.py, devoluciones, métodos de pago.

## Verificación
- .venv\Scripts\ruff check services scripts ; .venv\Scripts\pytest -q
- .\start-all.ps1 + smoke: login admin (PATCH umbral, PO→send→receive), login empleado (POST /sales de 2 ítems; GET /movements en :8002 muestra salidas reason=venta).

## Pendiente de decisión (pausa 2026-10-01)
- Idioma de los VALORES de enum (state, movement_type, reason, status de orden): hoy español, coherente con §4.2/§7 de ARCHITECTURE.md y con los datos ya sembrados por F-002. El usuario pregunta si deberían ser inglés. Si se cambia a inglés: migrar semilla + tests F-002, actualizar ARCHITECTURE.md y re-trabajar filtros de pasos 1-4. Decidir ANTES del paso 5.
