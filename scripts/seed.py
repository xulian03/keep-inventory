"""Semilla de datos de KeepInventory (F-002).

Fase 1 implementada en este archivo:
  - Paso 5: carga del catálogo completo BigBasket (todos los productos inactivos).
  - Paso 6: activación de 2000 productos por muestreo estratificado + proveedores.
  - Usuarios demo, 10 proveedores y 40 órdenes de compra con sus items (paso 8).

Fase 2 implementada en este archivo:
  - Paso 7: demanda esperada por producto (λ_p, pesos w_p, cuota, rate_p, E_p).
  - Paso 9: stocks objetivo por buckets exactos 100/300/1400/200.
  - Paso 10: ledger día a día (stock_movements + tickets en sales.db).
  - Paso 11: calibración final de stocks y umbrales.

Todas las fechas son relativas a "hoy" y toda la aleatoriedad proviene de una
única instancia random.Random(42) pasada explícitamente a cada función.
"""

import math
import random
import sys
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from time import perf_counter

# Permitir importar los paquetes de los servicios sin instalarlos.
_REPO_ROOT = Path(__file__).resolve().parent.parent
for _service_path in (
    _REPO_ROOT / "services" / "auth" / "src",
    _REPO_ROOT / "services" / "inventory" / "src",
    _REPO_ROOT / "services" / "sales" / "src",
):
    _path_str = str(_service_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

import pandas as pd  # noqa: E402
from auth import db as auth_db  # noqa: E402
from auth import models as auth_models  # noqa: E402
from auth.security import hash_password  # noqa: E402
from inventory import db as inventory_db  # noqa: E402
from inventory import models as inventory_models  # noqa: E402
from sales import db as sales_db  # noqa: E402
from sales import models as sales_models  # noqa: E402
from sqlalchemy import text  # noqa: E402

# Nota: la spec F-002 cita "data/Big Basket Products.csv", pero el CSV real del
# repo se llama "data/BigBasket Products.csv". Se usa el nombre real del fichero.
_CSV_PATH = _REPO_ROOT / "data" / "BigBasket Products.csv"

_SUPPLIERS = (
    ("Distribuidora Central", "contacto@distribuidoracentral.es"),
    ("Mayorista Nacional", "pedidos@mayoristanacional.es"),
    ("Grupo Levante", "ventas@grupolevante.es"),
    ("Comercial Ibérica", "compras@comercialiberica.es"),
    ("Almacenes del Sur", "info@almacenesdelsur.es"),
    ("Proveedora Mediterránea", "contacto@proveedoramediterranea.es"),
    ("Suministros Norte", "pedidos@suministrosnorte.es"),
    ("Logística Duero", "ventas@logisticaduero.es"),
    ("Importaciones Ebro", "compras@importacionesebro.es"),
    ("Mercados Andaluces", "info@mercadosandaluces.es"),
)

# Paso 7: base de demanda por categoría (una entrada por cada una de las 11
# categorías del catálogo, valor fijo entre 0.5 y 2.5).
_CATEGORY_BASE = {
    "Beauty & Hygiene": 1.0,
    "Gourmet & World Food": 0.8,
    "Kitchen, Garden & Pets": 0.6,
    "Snacks & Branded Foods": 2.0,
    "Foodgrains, Oil & Masala": 2.5,
    "Cleaning & Household": 0.9,
    "Beverages": 1.8,
    "Bakery, Cakes & Dairy": 1.6,
    "Baby Care": 0.5,
    "Fruits & Vegetables": 2.2,
    "Eggs, Meat & Fish": 1.4,
}

_DAYS = 180
_DAILY_UNITS = 165


def _seasonal_factor(day):
    """1.4 si el día cae en viernes, sábado o domingo reales; 1.0 el resto."""
    return 1.4 if day.weekday() >= 4 else 1.0


def _iso(day, hour, minute, second):
    """Timestamp ISO-8601 naive local para un día y una hora dados."""
    return datetime(day.year, day.month, day.day, hour, minute, second).isoformat(
        timespec="seconds"
    )


def _stock_state(product):
    """Estado de stock según ARCH §7 (calculado, no almacenado)."""
    if product.stock == 0:
        return "agotado"
    if product.stock <= product.min_threshold:
        return "bajo"
    if product.stock >= product.excess_threshold:
        return "exceso"
    return "disponible"


def _random_dt(today, offset, rng, start_hour=8, end_hour=17):
    """Fecha-hora aleatoria a `offset` días de hoy, con hora en el rango dado."""
    day = today + timedelta(days=offset)
    return datetime(
        day.year,
        day.month,
        day.day,
        rng.randint(start_hour, end_hour),
        rng.randint(0, 59),
        rng.randint(0, 59),
    )


def seed_users(session, rng, today):
    """3 usuarios demo con las credenciales de AGENTS.md."""
    created_at = datetime.combine(today - timedelta(days=200), time(9, 0, 0))
    users = [
        auth_models.User(
            name="Ana Dueña",
            email="admin@tienda.com",
            password_hash=hash_password("admin123"),
            role="admin",
            created_at=created_at.isoformat(timespec="seconds"),
        ),
        auth_models.User(
            name="Luis Empleado",
            email="empleado@tienda.com",
            password_hash=hash_password("empleado123"),
            role="empleado",
            created_at=created_at.isoformat(timespec="seconds"),
        ),
        auth_models.User(
            name="Marta Vendedora",
            email="vendedor2@tienda.com",
            password_hash=hash_password("vendedor123"),
            role="empleado",
            created_at=created_at.isoformat(timespec="seconds"),
        ),
    ]
    session.add_all(users)
    return users


def seed_suppliers(session, rng):
    """10 proveedores con lead_time aleatorio de 3 a 14 días."""
    suppliers = [
        inventory_models.Supplier(
            name=name,
            contact_email=email,
            lead_time_days=rng.randint(3, 14),
        )
        for name, email in _SUPPLIERS
    ]
    session.add_all(suppliers)
    return suppliers


def load_catalog(session, today):
    """Paso 5: carga el catálogo completo desde el CSV (todos inactivos)."""
    df = pd.read_csv(_CSV_PATH)
    df = df[df["product"].notna()]
    created_at = datetime.combine(today - timedelta(days=180), time(8, 0, 0))
    created_at_iso = created_at.isoformat(timespec="seconds")

    products = []
    for row in df.itertuples(index=False):
        brand = "" if pd.isna(row.brand) else str(row.brand)
        rating = None if pd.isna(row.rating) else float(row.rating)
        products.append(
            inventory_models.Product(
                name=str(row.product),
                brand=brand,
                category=str(row.category),
                subcategory=str(row.sub_category),
                type=str(row.type),
                sale_price=float(row.sale_price),
                market_price=float(row.market_price),
                rating=rating,
                is_active=0,
                stock=0,
                min_threshold=0,
                excess_threshold=0,
                supplier_id=None,
                created_at=created_at_iso,
            )
        )
    session.add_all(products)
    return products


def stratified_sample(pool, sample_size, rng):
    """Muestreo estratificado proporcional al tamaño de cada categoría.

    Reparte `sample_size` cupos entre las categorías de forma proporcional a su
    presencia en `pool` (método del mayor resto) y muestrea cada estrato con rng.
    """
    groups = {}
    for product in pool:
        groups.setdefault(product.category, []).append(product)

    total = len(pool)
    if sample_size >= total:
        return list(pool)

    categories = sorted(groups)
    exact = {c: len(groups[c]) * sample_size / total for c in categories}
    allocation = {c: int(exact[c]) for c in categories}
    remainder = sample_size - sum(allocation.values())
    by_fraction = sorted(categories, key=lambda c: (-(exact[c] - allocation[c]), c))
    for category in by_fraction[:remainder]:
        allocation[category] += 1

    selected = []
    for category in categories:
        selected.extend(rng.sample(groups[category], allocation[category]))
    return selected


def activate_products(session, products, suppliers, rng):
    """Paso 6: dedupe (producto, marca), activa 2000 y asigna proveedor.

    Los umbrales son provisionales (min=3, excess=10): los reescribe la
    calibración del paso 11.
    """
    seen = set()
    pool = []
    for product in products:
        key = (product.name, product.brand)
        if key in seen:
            continue
        seen.add(key)
        pool.append(product)

    active = stratified_sample(pool, 2000, rng)
    for product in active:
        product.is_active = 1
        product.min_threshold = 3
        product.excess_threshold = 10
        product.supplier_id = rng.choice(suppliers).id
    return active


def seed_purchase_orders(session, suppliers, active_products, rng, today):
    """Paso 8: 31 recibidas + 4 enviadas + 3 borrador + 2 canceladas con items."""
    by_supplier = {}
    for product in active_products:
        by_supplier.setdefault(product.supplier_id, []).append(product)

    orders = []

    for _ in range(31):
        supplier = rng.choice(suppliers)
        created = _random_dt(today, rng.randint(-170, -10), rng)
        expected = created + timedelta(days=supplier.lead_time_days)
        received = created + timedelta(
            days=supplier.lead_time_days + rng.randint(-2, 2)
        )
        yesterday = datetime.combine(today - timedelta(days=1), time(23, 59, 59))
        if received > yesterday:
            received = yesterday
        orders.append(
            inventory_models.PurchaseOrder(
                supplier_id=supplier.id,
                status="recibida",
                expected_date=expected.isoformat(timespec="seconds"),
                created_at=created.isoformat(timespec="seconds"),
                received_at=received.isoformat(timespec="seconds"),
            )
        )

    for _ in range(4):
        supplier = rng.choice(suppliers)
        created = _random_dt(today, rng.randint(-15, -5), rng)
        expected = datetime.combine(
            today + timedelta(days=rng.randint(1, 14)), time(12, 0, 0)
        )
        orders.append(
            inventory_models.PurchaseOrder(
                supplier_id=supplier.id,
                status="enviada",
                expected_date=expected.isoformat(timespec="seconds"),
                created_at=created.isoformat(timespec="seconds"),
                received_at=None,
            )
        )

    for _ in range(3):
        supplier = rng.choice(suppliers)
        created = _random_dt(today, rng.randint(-7, 0), rng)
        expected = datetime.combine(
            today + timedelta(days=rng.randint(7, 21)), time(12, 0, 0)
        )
        orders.append(
            inventory_models.PurchaseOrder(
                supplier_id=supplier.id,
                status="borrador",
                expected_date=expected.isoformat(timespec="seconds"),
                created_at=created.isoformat(timespec="seconds"),
                received_at=None,
            )
        )

    for _ in range(2):
        supplier = rng.choice(suppliers)
        created = _random_dt(today, rng.randint(-90, -30), rng)
        expected = created + timedelta(days=supplier.lead_time_days)
        orders.append(
            inventory_models.PurchaseOrder(
                supplier_id=supplier.id,
                status="cancelada",
                expected_date=expected.isoformat(timespec="seconds"),
                created_at=created.isoformat(timespec="seconds"),
                received_at=None,
            )
        )

    session.add_all(orders)
    session.flush()  # asigna ids sin commit para poder crear los items

    items = []
    for order in orders:
        supplier_products = by_supplier.get(order.supplier_id, [])
        if not supplier_products:
            continue
        count = min(rng.randint(5, 15), len(supplier_products))
        for product in rng.sample(supplier_products, count):
            items.append(
                inventory_models.PurchaseOrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=rng.randint(5, 60),
                    unit_cost=round(product.sale_price * rng.uniform(0.5, 0.7), 2),
                )
            )
    session.add_all(items)
    return orders, items


def compute_demand(active_products, rng, today):
    """Paso 7: λ_p, peso w_p, cuota share_p, tasa diaria rate_p y E_p.

    λ_p = base_categoría × U(0.5, 2.0); w_p = λ_p²; share_p = w_p/Σw;
    rate_p = 165 × share_p; S = Σ_{d=0..179} season(d)·trend(d);
    E_p = rate_p × S.
    """
    lambdas = {}
    for product in active_products:
        base = _CATEGORY_BASE.get(product.category, 1.0)
        lambdas[product.id] = base * rng.uniform(0.5, 2.0)

    weights = {pid: value * value for pid, value in lambdas.items()}
    total_weight = sum(weights.values())

    season_sum = 0.0
    for d in range(_DAYS):
        day = today + timedelta(days=-179 + d)
        season_sum += _seasonal_factor(day) * (1 + 0.002 * d)

    demand = {}
    for product in active_products:
        share = weights[product.id] / total_weight
        rate = _DAILY_UNITS * share
        demand[product.id] = {
            "rate": rate,
            "expected": rate * season_sum,
            "weight": weights[product.id],
        }
    return demand


def seed_target_stocks(active_products, demand, orders, items, rng):
    """Paso 9: buckets exactos, stock final objetivo y stock inicial.

    Reparte aleatoriamente 100 agotado / 300 bajo / 1400 disponible / 200
    exceso entre los activos, fija el stock objetivo e inicial de cada uno y
    descuenta del inicial la compra (`po_qty`) que llegará en la orden recibida.
    Devuelve (initial_stock, bucket_state).
    """
    buckets = (
        ["agotado"] * 100
        + ["bajo"] * 300
        + ["disponible"] * 1400
        + ["exceso"] * 200
    )
    rng.shuffle(buckets)

    initial_stock = {}
    bucket_state = {}
    for product, bucket in zip(active_products, buckets):
        rate = demand[product.id]["rate"]
        expected = demand[product.id]["expected"]
        if bucket == "agotado":
            final = 0
            initial = round(expected * rng.uniform(0.82, 0.95))
        else:
            if bucket == "bajo":
                final = max(1, round(rate * rng.uniform(1, 6)))
            elif bucket == "disponible":
                final = max(2, round(rate * rng.uniform(14, 45)))
            else:
                final = max(2, round(rate * rng.uniform(70, 130)))
            initial = round(expected * rng.uniform(1.02, 1.10)) + final
        initial_stock[product.id] = initial
        bucket_state[product.id] = bucket

    received_ids = {order.id for order in orders if order.status == "recibida"}
    for item in items:
        if item.order_id not in received_ids:
            continue
        pid = item.product_id
        po_qty = round(initial_stock[pid] * rng.uniform(0.25, 0.45))
        po_qty = min(po_qty, initial_stock[pid])
        item.quantity = po_qty
        initial_stock[pid] -= po_qty

    return initial_stock, bucket_state


def simulate_ledger(
    active_products, demand, initial_stock, orders, items, users, rng, today
):
    """Paso 10: ledger día a día (−180 inicial + −179..−1 con ventas).

    Devuelve (stock, movements, sales, sale_items) sin persistir.
    """
    weights = [demand[product.id]["weight"] for product in active_products]
    cumulative = []
    running = 0.0
    for weight in weights:
        running += weight
        cumulative.append(running)

    user_ids = {user.email: user.id for user in users}
    employee_id = user_ids["empleado@tienda.com"]
    vendedor_id = user_ids["vendedor2@tienda.com"]
    admin_id = user_ids["admin@tienda.com"]

    order_by_id = {order.id: order for order in orders}
    arrivals = {}
    for item in items:
        order = order_by_id.get(item.order_id)
        if order is None or order.status != "recibida" or order.received_at is None:
            continue
        arrivals.setdefault(order.received_at[:10], []).append((order.id, item))

    adjustments = {}
    for _ in range(50):
        offset = rng.randint(-180, -1)
        product = active_products[rng.randrange(len(active_products))]
        is_entry = rng.random() < 0.5
        quantity = rng.randint(1, 10)
        day = today + timedelta(days=offset)
        created = _iso(day, rng.randint(8, 20), rng.randint(0, 59), rng.randint(0, 59))
        adjustments.setdefault(offset, []).append(
            (product.id, is_entry, quantity, created)
        )

    movements = []
    sales = []
    sale_items = []
    sale_id = 0
    stock = dict(initial_stock)

    initial_created = _iso(today - timedelta(days=180), 8, 0, 0)
    for product in active_products:
        quantity = stock[product.id]
        if quantity <= 0:
            continue
        movements.append(
            inventory_models.StockMovement(
                product_id=product.id,
                movement_type="entrada",
                quantity=quantity,
                reason="ajuste",
                reference="stock inicial",
                created_at=initial_created,
            )
        )

    for offset in range(-179, 0):
        day = today + timedelta(days=offset)
        season = _seasonal_factor(day)
        trend = 1 + 0.002 * (offset + 179)

        for order_id, item in arrivals.get(day.isoformat(), []):
            if item.quantity <= 0:
                continue
            created = _iso(
                day, rng.randint(9, 17), rng.randint(0, 59), rng.randint(0, 59)
            )
            movements.append(
                inventory_models.StockMovement(
                    product_id=item.product_id,
                    movement_type="entrada",
                    quantity=item.quantity,
                    reason="compra",
                    reference=f"po:{order_id}",
                    created_at=created,
                )
            )
            stock[item.product_id] += item.quantity

        n_tickets = round(rng.uniform(15, 40) * season * trend)
        for _ in range(n_tickets):
            created = _iso(
                day, rng.randint(8, 20), rng.randint(0, 59), rng.randint(0, 59)
            )
            draw = rng.random()
            if draw < 0.70:
                employee = employee_id
            elif draw < 0.95:
                employee = vendedor_id
            else:
                employee = admin_id

            lines = []
            for _ in range(rng.randint(1, 5)):
                product = rng.choices(
                    active_products, cum_weights=cumulative, k=1
                )[0]
                sold = min(rng.randint(1, 3), stock[product.id])
                if sold <= 0:
                    continue
                stock[product.id] -= sold
                lines.append((product, sold))

            if not lines:
                continue
            sale_id += 1
            total = 0.0
            for product, sold in lines:
                unit_price = product.sale_price
                line_total = sold * unit_price
                total += line_total
                movements.append(
                    inventory_models.StockMovement(
                        product_id=product.id,
                        movement_type="salida",
                        quantity=sold,
                        reason="venta",
                        reference=f"sale:{sale_id}",
                        created_at=created,
                    )
                )
                sale_items.append(
                    sales_models.SaleItem(
                        sale_id=sale_id,
                        product_id=product.id,
                        product_name=product.name,
                        category=product.category,
                        quantity=sold,
                        unit_price=unit_price,
                        line_total=line_total,
                    )
                )
            sales.append(
                sales_models.Sale(
                    id=sale_id,
                    employee_id=employee,
                    total=total,
                    created_at=created,
                )
            )

        for product_id, is_entry, quantity, created in adjustments.get(offset, []):
            if is_entry:
                stock[product_id] += quantity
                movements.append(
                    inventory_models.StockMovement(
                        product_id=product_id,
                        movement_type="entrada",
                        quantity=quantity,
                        reason="ajuste",
                        reference="ajuste manual",
                        created_at=created,
                    )
                )
            else:
                sold = min(quantity, stock[product_id])
                if sold <= 0:
                    continue
                stock[product_id] -= sold
                movements.append(
                    inventory_models.StockMovement(
                        product_id=product_id,
                        movement_type="salida",
                        quantity=sold,
                        reason="ajuste",
                        reference="ajuste manual",
                        created_at=created,
                    )
                )

    return stock, movements, sales, sale_items


def calibrate(active_products, demand, stock, bucket_state, today):
    """Paso 11: calibración final por ranking de cobertura y umbrales.

    Devuelve la lista de movimientos de ajuste/cierre fechados ayer a las 23:00.
    """
    created = _iso(today - timedelta(days=1), 23, 0, 0)
    movements = []

    # (a) los activos a 0 fuera del bucket agotado recuperan stock.
    for product in active_products:
        pid = product.id
        if stock[pid] == 0 and bucket_state[pid] != "agotado":
            quantity = max(1, round(demand[pid]["rate"] * 3))
            stock[pid] += quantity
            movements.append(
                inventory_models.StockMovement(
                    product_id=pid,
                    movement_type="entrada",
                    quantity=quantity,
                    reason="ajuste",
                    reference="ajuste final",
                    created_at=created,
                )
            )

    # (b) ranking ascendente por cobertura = stock / rate (empates por id).
    ranked = sorted(
        active_products,
        key=lambda product: (
            stock[product.id] / max(demand[product.id]["rate"], 1e-9),
            product.id,
        ),
    )

    for index, product in enumerate(ranked):
        pid = product.id
        if index < 100:
            if stock[pid] > 0:
                quantity = stock[pid]
                stock[pid] = 0
                movements.append(
                    inventory_models.StockMovement(
                        product_id=pid,
                        movement_type="salida",
                        quantity=quantity,
                        reason="ajuste",
                        reference="cierre",
                        created_at=created,
                    )
                )
            product.min_threshold = 3
            product.excess_threshold = 10
        elif index < 400:
            product.min_threshold = max(1, stock[pid])
            product.excess_threshold = max(
                product.min_threshold + 1, round(demand[pid]["rate"] * 60)
            )
        elif index < 1800:
            product.min_threshold = min(
                max(3, math.floor(stock[pid] * 0.5)), stock[pid] - 1
            )
            product.excess_threshold = max(
                stock[pid] + 1, product.min_threshold + 1
            )
        else:
            product.min_threshold = min(
                max(3, math.ceil(demand[pid]["rate"] * 7)), stock[pid] - 1
            )
            product.excess_threshold = max(1, round(stock[pid] * 0.8))

    for product in active_products:
        product.stock = stock[product.id]

    return movements


def _prepare_databases():
    """Borra las .db existentes y devuelve engines y sesiones recreados."""
    engines = [
        auth_db.get_engine(),
        inventory_db.get_engine(),
        sales_db.get_engine(),
    ]
    for engine in engines:
        db_path = Path(engine.url.database)
        engine.dispose()
        if db_path.exists():
            db_path.unlink()

    auth_engine = auth_db.get_engine()
    inventory_engine = inventory_db.get_engine()
    sales_engine = sales_db.get_engine()

    auth_models.Base.metadata.create_all(auth_engine)
    inventory_models.Base.metadata.create_all(inventory_engine)
    sales_models.Base.metadata.create_all(sales_engine)

    return auth_engine, inventory_engine, sales_engine


def print_summary(
    auth_session, inventory_session, sales_session, orders, active_products, elapsed
):
    """Resumen en español: recuentos, estados, invariant de ledger y tiempo."""
    status_counts = Counter(order.status for order in orders)
    n_users = auth_session.query(auth_models.User).count()
    n_suppliers = inventory_session.query(inventory_models.Supplier).count()
    n_products = inventory_session.query(inventory_models.Product).count()
    n_active = (
        inventory_session.query(inventory_models.Product)
        .filter(inventory_models.Product.is_active == 1)
        .count()
    )
    n_movements = inventory_session.query(inventory_models.StockMovement).count()
    n_orders = inventory_session.query(inventory_models.PurchaseOrder).count()
    n_items = inventory_session.query(inventory_models.PurchaseOrderItem).count()
    n_sales = sales_session.query(sales_models.Sale).count()
    n_sale_items = sales_session.query(sales_models.SaleItem).count()

    state_counts = Counter(_stock_state(product) for product in active_products)

    violations = inventory_session.execute(
        text(
            "SELECT COUNT(*) FROM ("
            " SELECT p.id AS id, p.stock AS stock,"
            " COALESCE(SUM(CASE WHEN m.movement_type = 'entrada'"
            " THEN m.quantity ELSE -m.quantity END), 0) AS net"
            " FROM products p LEFT JOIN stock_movements m ON m.product_id = p.id"
            " WHERE p.is_active = 1 GROUP BY p.id"
            ") WHERE stock != net"
        )
    ).scalar()

    print("=== Semilla KeepInventory - F-002 ===")
    print(f"auth.db       users={n_users}")
    print(
        f"inventory.db  suppliers={n_suppliers} products={n_products} "
        f"(activos={n_active})"
    )
    print(
        f"              stock_movements={n_movements} "
        f"purchase_orders={n_orders} purchase_order_items={n_items}"
    )
    print(f"sales.db      sales={n_sales} sale_items={n_sale_items}")
    print("Ordenes de compra por estado:")
    for status in ("borrador", "enviada", "recibida", "cancelada"):
        print(f"  {status}: {status_counts.get(status, 0)}")
    print("Distribucion de estados de stock (2000 activos):")
    for state in ("agotado", "bajo", "disponible", "exceso"):
        print(f"  {state}: {state_counts.get(state, 0)}")
    print(
        "Invariant ledger (products.stock == entradas - salidas activos): "
        f"{violations} violaciones"
    )
    print(f"Tiempo de ejecucion: {elapsed:.2f} s")


def run():
    """Recrea las 3 BD y ejecuta las fases implementadas de la semilla."""
    rng = random.Random(42)
    today = date.today()
    started = perf_counter()

    auth_engine, inventory_engine, sales_engine = _prepare_databases()
    auth_session = auth_db.get_session_factory(auth_engine)()
    inventory_session = inventory_db.get_session_factory(inventory_engine)()
    sales_session = sales_db.get_session_factory(sales_engine)()

    users = seed_users(auth_session, rng, today)
    auth_session.commit()

    suppliers = seed_suppliers(inventory_session, rng)
    inventory_session.commit()

    products = load_catalog(inventory_session, today)
    inventory_session.commit()

    active_products = activate_products(inventory_session, products, suppliers, rng)
    inventory_session.commit()

    orders, items = seed_purchase_orders(
        inventory_session, suppliers, active_products, rng, today
    )
    inventory_session.commit()

    demand = compute_demand(active_products, rng, today)
    initial_stock, bucket_state = seed_target_stocks(
        active_products, demand, orders, items, rng
    )

    stock, movements, sales, sale_items = simulate_ledger(
        active_products, demand, initial_stock, orders, items, users, rng, today
    )
    movements.extend(calibrate(active_products, demand, stock, bucket_state, today))

    inventory_session.add_all(movements)
    sales_session.add_all(sales)
    sales_session.add_all(sale_items)
    inventory_session.commit()
    sales_session.commit()

    elapsed = perf_counter() - started
    print_summary(
        auth_session,
        inventory_session,
        sales_session,
        orders,
        active_products,
        elapsed,
    )

    auth_session.close()
    inventory_session.close()
    sales_session.close()
    # Liberar los ficheros SQLite (evita bloqueos al borrar temporales en Windows).
    auth_engine.dispose()
    inventory_engine.dispose()
    sales_engine.dispose()


if __name__ == "__main__":
    run()
