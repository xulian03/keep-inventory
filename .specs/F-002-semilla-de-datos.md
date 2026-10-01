# Spec F-002 — Semilla de datos

## Objetivo
Crear scripts/seed.py que genere las 3 bases de datos (auth.db, inventory.db, sales.db) con
datos de demo listos para sustentar las features F-003+: catálogo completo BigBasket,
usuarios demo, 10 proveedores, ~40 órdenes de compra, ~180 días de tickets de venta y stock
coherente (ledger: todo cambio de stock queda registrado como movimiento) con los 4 estados
calibrados (~5% agotado, ~15% bajo, ~70% disponible, ~10% exceso). Todo determinista
(semilla aleatoria fija) y fechado relativo a "hoy" en tiempo de ejecución, para que la
demo siempre muestre datos recientes.

Decisión de usuario (2026-10-01): models.py (SQLAlchemy) viven en cada servicio y la
semilla los importa; re-ejecutar recrea las BD desde cero; catálogo completo (27.554
filas, dedupe solo para elegir los ~2000 activos); simulación día a día (ledger); muestreo
estratificado proporcional por categoría con semilla fija.

## Archivos afectados
- Nuevos services/auth/src/auth/: models.py (User), db.py (get_engine sobre AUTH_DB),
  security.py (hash_password/verify_password PBKDF2-SHA256, reutilizado por F-003).
- Nuevos services/inventory/src/inventory/: models.py (Supplier, Product, StockMovement,
  PurchaseOrder, PurchaseOrderItem + índices de ARCH §4.2), db.py (INVENTORY_DB).
- Nuevos services/sales/src/sales/: models.py (Sale, SaleItem), db.py (SALES_DB).
- Nuevo scripts/seed.py: toda la lógica de semillado, ejecutable y con funciones puras
  testables; inserta services/*/src en sys.path para importar los paquetes.
- Nuevo scripts/tests/test_seed.py: tests de invariants (ver abajo).
- Actualizar pyproject.toml: testpaths += "scripts/tests", pythonpath += "scripts".
- Actualizar services/auth/src/auth/config.py (+AUTH_DB), inventory/config.py
  (+INVENTORY_DB), sales/config.py (+SALES_DB), defaults "auth.db"/"inventory.db"/
  "sales.db" (relativos al CWD: raíz del repo).

## Decisiones técnicas concretas
- models.py = clases declarativas puras (sin engine global); db.py expone get_engine()
  que lee la ruta desde config en cada llamada → los tests pueden redirigir con variables
  de entorno a ficheros temporales.
- Contraseñas PBKDF2-SHA256, 100.000 iteraciones, salt aleatorio de 16 bytes;
  formato "pbkdf2_sha256$<iteraciones>$<salt_hex>$<hash_hex>".
- BD en la raíz del repo (CWD) — cubiertas por *.db en .gitignore. La semilla las borra
  y recrea con Base.metadata.drop_all/create_all.
- Fechas ISO-8601 naive local "YYYY-MM-DDTHH:MM:SS". Días simulados: -179..-1 (hasta
  ayer). Aleatoriedad: una única instancia random.Random(42).
- Inventario inicial = movimiento entrada reason=ajuste ("stock inicial") en el día
  -180 → invariant: products.stock == Σ entradas − Σ salidas por producto (verificable).
- Simulación orientada a objetivo (corrige el borrador v1, cuyo flujo de compras no
  cubría la demanda y degeneraba en ~85% agotados): primero se fija el stock final
  objetivo por producto (según su cuota de demanda esperada) y el stock inicial se
  calcula para llegar a él; la simulación día a día aplica ruido, y la calibración final
  por ranking de "días de cobertura" garantiza la distribución exacta.
- La demanda diaria NO es λ_p absoluto: los tickets (15–40/día × 1–5 líneas × cant
  1–3) son la fuente real de volumen (~165 uds/día); λ_p solo pondera la popularidad
  (peso = λ_p²) y la cuota resultante define demanda esperada y umbrales.

## Pasos atómicos
1. config.py de cada servicio: añadir AUTH_DB / INVENTORY_DB / SALES_DB (getenv con
   default), sin tocar lo existente.
2. auth: db.py + models.py (User: name, email UNIQUE, password_hash, role CHECK
   admin|empleado, created_at) + security.py (hash_password, verify_password).
3. inventory: db.py + models.py con el esquema y CHECKs/índices exactos de ARCH §4.2
   (products.category, products.is_active, stock_movements(product_id, created_at),
   purchase_orders(status, created_at)) + db.py.
4. sales: models.py (Sale, SaleItem con campos denormalizados) + db.py.
5. scripts/seed.py — carga de catálogo: leer data/"BigBasket Products.csv" con pandas,
   saltar filas con product nulo, rellenar brand nulo con "", insertar 27.554 productos
   (is_active=0, stock=0, umbrales 0, supplier NULL, created_at = hoy−180d).
6. seed — activos: pool dedupe (product+brand) → muestreo estratificado proporcional por
   categoría de 2000 activos; asignar proveedor (1 de 10). Umbrales provisionales
   min=3/excess=10 (los reescribe la calibración; inactivos quedan en 0/0).
7. seed — demanda esperada: λ_p = base por categoría (0.5–2.5) × U(0.5, 2.0); peso de
   selección w_p = λ_p²; cuota share_p = w_p/Σw; tasa diaria rate_p = 165 × share_p
   unidades/día (165 = 27.5 tickets × 3 líneas × 2 uds esperadas); S = Σ_{d=0..179}
   season(d)·trend(d) con season = 1.4 vie/sáb/dom, trend = 1+0.002·d; demanda esperada
   E_p = rate_p × S. Los tickets del día usan n = round(U(15,40)·season·trend).
8. seed — órdenes de compra: 10 proveedores (lead_time 3–14 días); 40 órdenes: 31
   recibidas (created_at repartido en −170..−10, received_at = created + lead_time ± 2,
   dentro de la ventana simulada), 4 enviadas (created hace 5–15 días, expected_date
   futura 1–14 días), 3 borrador (created hace 0–7 días), 2 canceladas (created hace
   30–90 días); items: 5–15 por orden (productos activos del proveedor), quantity 5–60,
   unit_cost = sale_price × U(0.5, 0.7). Solo las recibidas afectan stock.
9. seed — stocks objetivo: reparto aleatorio fijado de buckets entre los 2000 activos:
   100 agotado / 300 bajo / 1400 disponible / 200 exceso. Stock final objetivo:
   agotado → 0; bajo → max(1, round(rate_p × U(1, 6))); disponible →
   max(2, round(rate_p × U(14, 45))); exceso → max(2, round(rate_p × U(70, 130))).
   Stock inicial: agotado → round(E_p × U(0.82, 0.95)) (se agota en el tramo final);
   resto → round(E_p × U(1.02, 1.10)) + objetivo. Productos con item en una orden
   recibida: po_qty = round(inicial × U(0.25, 0.45)) se resta del inicial y llega como
   entrada reason=compra (reference="po:<id>") en received_at.
10. seed — ledger día a día (−179..−1): stock inicial como entrada reason=ajuste
    (reference="stock inicial", día −180); por día: entradas de órdenes recibidas ese
    día (hora 09:00–17:00); tickets: líneas con producto por pesos w_p (random.choices),
    cantidad 1–3, se vende min(cant, stock) y con stock 0 la línea se descarta → salida
    reason=venta (reference="sale:<id>"); empleado del ticket: 70% empleado,
    25% vendedor2, 5% admin; hora aleatoria 08:00–20:00; ~50 movimientos ajuste
    dispersos (entrada/salida, cant 1–10, reference="ajuste manual"). La venta se
    escribe en sales.db con los campos denormalizados del CSV (product_name, category,
    unit_price=sale_price, line_total).
11. seed — calibración final (por ranking de cobertura = stock/rate_p, empates por id):
    (a) todo activo con stock 0 fuera del bucket agotado recibe entrada reason=ajuste
    (reference="ajuste final", cantidad max(1, round(rate_p × 3)));
    (b) ranking ascendente: 100 primeros → agotado (si stock > 0: salida reason=ajuste
    reference="cierre" con todo el stock), 300 siguientes → bajo, 1400 → disponible,
    200 últimos → exceso;
    (c) umbrales definitivos: agotado → 3/10; bajo → min=max(1, stock),
    excess=max(min+1, round(rate_p × 60)); disponible → min=min(max(3,
    floor(stock × 0.5)), stock−1), excess=max(stock+1, min+1); exceso →
    min=min(max(3, ceil(rate_p × 7)), stock−1), excess=max(1, round(stock × 0.8));
    (d) invariant de ledger + resumen (recuentos por tabla + distribución de estados).
12. scripts/tests/test_seed.py: con env apuntando a DBs temporales: ejecutar la semilla
    una vez (fixture de sesión) y verificar: 3 usuarios (email UNIQUE, roles válidos,
    verify_password correcto con admin123/empleado123/vendedor123), 27.554 productos,
    2000 activos, 40 órdenes (31/4/3/2 por estado), tickets totales en 2.700–7.200,
    Σ línea-ventas > 0, invariant de ledger en TODOS los activos, distribución de
    estados dentro de ±3 puntos de los targets (o exacta en recuentos de bucket si la
    calibración la fuerza), y fechas de ventas dentro de los 180 días. Además un test
    unitario de hash_password/verify_password y de la estratificación.
13. pyproject.toml: testpaths/pythonpath según "Archivos afectados".

## Criterios de aceptación
1. .venv\Scripts\python scripts\seed.py → exit 0 en < 2 min, crea auth.db, inventory.db,
   sales.db en la raíz e imprime el resumen con la distribución de estados.
2. Invariant de ledger: para cada producto activo, products.stock == Σ movimientos
   entrada − Σ movimientos salida (verificado por test y por el resumen).
3. Distribución de estados de los 2000 activos ≈ 5% agotado / 15% bajo / 70%
   disponible / 10% exceso (±3 puntos, verificado por test).
4. Contraseñas verificables: hash_password/verify_password redondos con las 3
   credenciales demo (test unitario).
5. .venv\Scripts\pytest -q → todos los tests (services + scripts) en verde.
6. .venv\Scripts\ruff check services scripts → sin errores.
7. Re-ejecutar seed.py produce resultados idénticos en recuentos (determinismo salvo
   fechas/horas derivadas de "hoy").

## Fuera de alcance
- Endpoints de negocio, login/JWT (F-003), cualquier endpoint REST distinto de /health
  existente; frontend; documentación README (F-013); carga de datos vía API; borrar el
  CSV; cambiar ARCHITECTURE.md (esta spec la implementa tal cual §4 y §11).

## Comandos de verificación
```
# desde la raíz (requiere .venv instalado y el CSV en data/):
.venv\Scripts\python scripts\seed.py
.venv\Scripts\pytest -q                      # services + scripts/tests
.venv\Scripts\ruff check services scripts
# inspección manual rápida de recuentos:
.venv\Scripts\python -c "import sqlite3; [print(n, sqlite3.connect(n).execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]) for n, t in [('auth.db','users'),('inventory.db','products'),('inventory.db','stock_movements'),('inventory.db','purchase_orders'),('sales.db','sales'),('sales.db','sale_items')]]"
```
