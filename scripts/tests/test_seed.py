"""Tests de la semilla de datos (F-002).

Los tests de integración comparten una única ejecución de la semilla sobre
bases de datos temporales (fixture de sesión); los unitarios no tocan BD.
"""

import os
import random
import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
import seed
from auth.security import hash_password, verify_password

_USERS = {
    "admin@tienda.com": ("admin123", "admin"),
    "empleado@tienda.com": ("empleado123", "empleado"),
    "vendedor2@tienda.com": ("vendedor123", "empleado"),
}

_TARGET_STATES = {"agotado": 100, "bajo": 300, "disponible": 1400, "exceso": 200}

# Invariant de ledger: stock == entradas - salidas para cada producto activo.
_LEDGER_SQL = (
    "SELECT COUNT(*) FROM ("
    " SELECT p.id AS id, p.stock AS stock,"
    " COALESCE(SUM(CASE WHEN m.movement_type = 'entrada'"
    " THEN m.quantity ELSE -m.quantity END), 0) AS net"
    " FROM products p LEFT JOIN stock_movements m ON m.product_id = p.id"
    " WHERE p.is_active = 1 GROUP BY p.id"
    ") WHERE stock != net"
)


@pytest.fixture(scope="session")
def seeded_dbs(tmp_path_factory):
    """Ejecuta la semilla una sola vez sobre SQLite temporales y expone rutas."""
    db_dir = tmp_path_factory.mktemp("seed_dbs")
    paths = {
        "auth": db_dir / "auth.db",
        "inventory": db_dir / "inventory.db",
        "sales": db_dir / "sales.db",
    }
    env_keys = {"auth": "AUTH_DB", "inventory": "INVENTORY_DB", "sales": "SALES_DB"}
    previous = {key: os.environ.get(key) for key in env_keys.values()}
    for name, key in env_keys.items():
        os.environ[key] = str(paths[name])
    try:
        seed.run()
        yield paths
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _rows(path, query, params=()):
    connection = sqlite3.connect(str(path))
    try:
        return connection.execute(query, params).fetchall()
    finally:
        connection.close()


def _scalar(path, query, params=()):
    return _rows(path, query, params)[0][0]


def _stock_state(stock, min_threshold, excess_threshold):
    """Estado de stock segun ARCH §7 (independiente de seed)."""
    if stock == 0:
        return "agotado"
    if stock <= min_threshold:
        return "bajo"
    if stock >= excess_threshold:
        return "exceso"
    return "disponible"


# --- Integracion sobre las BD temporales (paso 12) ---


def test_users_seeded_with_unique_emails_and_valid_roles(seeded_dbs):
    rows = _rows(seeded_dbs["auth"], "SELECT email, password_hash, role FROM users")
    assert len(rows) == 3
    emails = [row[0] for row in rows]
    assert sorted(emails) == sorted(_USERS)
    assert len(set(emails)) == 3
    for email, password_hash, role in rows:
        password, expected_role = _USERS[email]
        assert role == expected_role
        assert role in {"admin", "empleado"}
        assert verify_password(password, password_hash) is True


def test_catalog_and_active_product_counts(seeded_dbs):
    inventory = seeded_dbs["inventory"]
    assert _scalar(inventory, "SELECT COUNT(*) FROM products") == 27554
    assert _scalar(inventory, "SELECT COUNT(*) FROM products WHERE is_active = 1") == 2000


def test_purchase_orders_by_status(seeded_dbs):
    rows = _rows(
        seeded_dbs["inventory"],
        "SELECT status, COUNT(*) FROM purchase_orders GROUP BY status",
    )
    counts = dict(rows)
    assert counts.get("recibida") == 31
    assert counts.get("enviada") == 4
    assert counts.get("borrador") == 3
    assert counts.get("cancelada") == 2


def test_sales_volume_and_recent_dates(seeded_dbs):
    sales = seeded_dbs["sales"]
    total = _scalar(sales, "SELECT COUNT(*) FROM sales")
    assert 2700 <= total <= 7200
    assert _scalar(sales, "SELECT COUNT(*) FROM sale_items") > 0
    today = date.today()
    earliest = today - timedelta(days=180)
    for (created_at,) in _rows(sales, "SELECT created_at FROM sales"):
        assert earliest <= datetime.fromisoformat(created_at).date() <= today


def test_ledger_invariant_holds_for_all_active_products(seeded_dbs):
    assert _scalar(seeded_dbs["inventory"], _LEDGER_SQL) == 0


def test_no_active_product_has_negative_stock(seeded_dbs):
    count = _scalar(
        seeded_dbs["inventory"],
        "SELECT COUNT(*) FROM products WHERE is_active = 1 AND stock < 0",
    )
    assert count == 0


def test_stock_state_distribution_matches_targets(seeded_dbs):
    rows = _rows(
        seeded_dbs["inventory"],
        "SELECT stock, min_threshold, excess_threshold FROM products"
        " WHERE is_active = 1",
    )
    counts = Counter(
        _stock_state(stock, min_threshold, excess_threshold)
        for stock, min_threshold, excess_threshold in rows
    )
    total = len(rows)
    assert total == 2000
    tolerance = total * 0.03  # 3 puntos porcentuales
    for state, target in _TARGET_STATES.items():
        assert abs(counts[state] - target) <= tolerance


def test_calibration_movements_exist_and_are_positive(seeded_dbs):
    rows = _rows(
        seeded_dbs["inventory"],
        "SELECT reference, movement_type, COUNT(*), MIN(quantity) FROM stock_movements"
        " WHERE reference IN ('cierre', 'ajuste final')"
        " GROUP BY reference, movement_type",
    )
    by_key = {(ref, kind): (count, min_qty) for ref, kind, count, min_qty in rows}
    assert ("cierre", "salida") in by_key
    assert by_key[("cierre", "salida")][0] > 0
    assert ("ajuste final", "entrada") in by_key
    assert by_key[("ajuste final", "entrada")][0] > 0
    for count, min_qty in by_key.values():
        assert count > 0
        assert min_qty > 0


# --- Unitarios (paso 12) ---


def test_hash_password_roundtrip():
    stored = hash_password("secreta")
    assert verify_password("secreta", stored) is True
    assert verify_password("otra", stored) is False


def test_verify_password_malformed_returns_false():
    for stored in ("", "sin-formato", "pbkdf2_sha256$abc", "otro$1$00$00"):
        assert verify_password("secreta", stored) is False


def _synthetic_pool():
    return (
        [SimpleNamespace(category="A") for _ in range(50)]
        + [SimpleNamespace(category="B") for _ in range(30)]
        + [SimpleNamespace(category="C") for _ in range(20)]
    )


def test_stratified_sample_proportional_allocation():
    selected = seed.stratified_sample(_synthetic_pool(), 10, random.Random(1))
    counts = Counter(item.category for item in selected)
    assert len(selected) == 10
    assert counts == {"A": 5, "B": 3, "C": 2}


def test_stratified_sample_largest_remainder():
    selected = seed.stratified_sample(_synthetic_pool(), 7, random.Random(1))
    counts = Counter(item.category for item in selected)
    assert sum(counts.values()) == 7
    assert counts == {"A": 4, "B": 2, "C": 1}


def test_stratified_sample_returns_whole_pool_when_size_exceeds():
    pool = [SimpleNamespace(category="A") for _ in range(3)]
    assert seed.stratified_sample(pool, 5, random.Random(1)) == pool
