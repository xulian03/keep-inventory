"""Tests del CRUD de órdenes de compra (F-004, paso 4).

Usa la fixture seeded_db de conftest.py, que siembra proveedor, productos y tres
órdenes fijas (dos borrador y una enviada) con fechas deterministas.
"""

import pytest
from fastapi.testclient import TestClient
from inventory import rbac
from inventory.main import app

_HEADERS = {"Authorization": f"Bearer {rbac.create_access_token(1, 'admin', 'Admin')}"}
_EMPLOYEE_HEADERS = {
    "Authorization": f"Bearer {rbac.create_access_token(2, 'empleado', 'Empleado')}"
}


def _payload(seeded_db, items, expected_date="2026-10-05T12:00:00"):
    return {
        "supplier_id": seeded_db["supplier"],
        "expected_date": expected_date,
        "items": items,
    }


def test_post_crea_borrador_con_total(seeded_db):
    payload = _payload(
        seeded_db,
        [
            {"product_id": seeded_db["disponible"], "quantity": 2, "unit_cost": 1.5},
            {"product_id": seeded_db["bajo"], "quantity": 3, "unit_cost": 2.0},
        ],
    )
    with TestClient(app) as client:
        response = client.post("/purchase-orders", json=payload, headers=_HEADERS)
        order_id = response.json().get("id")
        detalle = client.get(f"/purchase-orders/{order_id}", headers=_HEADERS)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "borrador"
    assert body["expected_date"] == "2026-10-05T12:00:00"
    assert body["item_count"] == 2
    assert body["total"] == pytest.approx(9.0)
    assert len(body["items"]) == 2
    assert {item["total"] for item in body["items"]} == {3.0, 6.0}
    assert detalle.status_code == 200
    assert detalle.json()["total"] == pytest.approx(9.0)
    assert detalle.json()["item_count"] == 2


def test_post_sin_expected_date_usa_default(seeded_db):
    payload = {
        "supplier_id": seeded_db["supplier"],
        "items": [
            {"product_id": seeded_db["disponible"], "quantity": 1, "unit_cost": 1.0}
        ],
    }
    with TestClient(app) as client:
        response = client.post("/purchase-orders", json=payload, headers=_HEADERS)

    assert response.status_code == 201
    assert response.json()["expected_date"]


def test_post_422_proveedor_inexistente(seeded_db):
    payload = {
        "supplier_id": 999999,
        "items": [
            {"product_id": seeded_db["disponible"], "quantity": 1, "unit_cost": 1.0}
        ],
    }
    with TestClient(app) as client:
        response = client.post("/purchase-orders", json=payload, headers=_HEADERS)
    assert response.status_code == 422


def test_post_422_producto_inexistente(seeded_db):
    payload = _payload(
        seeded_db, [{"product_id": 999999, "quantity": 1, "unit_cost": 1.0}]
    )
    with TestClient(app) as client:
        response = client.post("/purchase-orders", json=payload, headers=_HEADERS)
    assert response.status_code == 422


def test_post_422_items_vacio(seeded_db):
    payload = _payload(seeded_db, [])
    with TestClient(app) as client:
        response = client.post("/purchase-orders", json=payload, headers=_HEADERS)
    assert response.status_code == 422


def test_post_422_duplicados(seeded_db):
    payload = _payload(
        seeded_db,
        [
            {"product_id": seeded_db["disponible"], "quantity": 1, "unit_cost": 1.0},
            {"product_id": seeded_db["disponible"], "quantity": 2, "unit_cost": 2.0},
        ],
    )
    with TestClient(app) as client:
        response = client.post("/purchase-orders", json=payload, headers=_HEADERS)
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("quantity", "unit_cost"),
    [(0, 1.0), (-1, 1.0), (1, -0.1)],
)
def test_post_422_cantidad_o_costo_invalido(seeded_db, quantity, unit_cost):
    payload = _payload(
        seeded_db,
        [
            {
                "product_id": seeded_db["disponible"],
                "quantity": quantity,
                "unit_cost": unit_cost,
            }
        ],
    )
    with TestClient(app) as client:
        response = client.post("/purchase-orders", json=payload, headers=_HEADERS)
    assert response.status_code == 422


def test_get_lista_total_item_count_y_orden(seeded_db):
    with TestClient(app) as client:
        response = client.get("/purchase-orders", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == seeded_db["total_ordenes"]
    assert body["page"] == 1
    assert body["page_size"] == 50
    ids = [item["id"] for item in body["items"]]
    assert ids == [
        seeded_db["po_borrador2"],
        seeded_db["po_enviada"],
        seeded_db["po_borrador"],
    ]
    por_id = {item["id"]: item for item in body["items"]}
    assert por_id[seeded_db["po_borrador"]]["total"] == pytest.approx(
        seeded_db["po_borrador_total"]
    )
    assert por_id[seeded_db["po_borrador"]]["item_count"] == 2
    assert por_id[seeded_db["po_enviada"]]["total"] == pytest.approx(
        seeded_db["po_enviada_total"]
    )
    assert por_id[seeded_db["po_enviada"]]["item_count"] == 1
    assert por_id[seeded_db["po_borrador2"]]["total"] == pytest.approx(
        seeded_db["po_borrador2_total"]
    )


def test_get_lista_filtro_status(seeded_db):
    with TestClient(app) as client:
        response = client.get(
            "/purchase-orders", params={"status": "borrador"}, headers=_HEADERS
        )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert all(item["status"] == "borrador" for item in body["items"])


def test_get_lista_filtro_supplier(seeded_db):
    with TestClient(app) as client:
        existente = client.get(
            "/purchase-orders",
            params={"supplier_id": seeded_db["supplier"]},
            headers=_HEADERS,
        )
        inexistente = client.get(
            "/purchase-orders", params={"supplier_id": 999999}, headers=_HEADERS
        )
    assert existente.status_code == 200
    assert existente.json()["total"] == seeded_db["total_ordenes"]
    assert inexistente.json()["total"] == 0


def test_get_lista_filtro_fechas_inclusivo_fecha_sola(seeded_db):
    with TestClient(app) as client:
        del_dia = client.get(
            "/purchase-orders",
            params={"date_from": "2026-09-22", "date_to": "2026-09-22"},
            headers=_HEADERS,
        )
        rango = client.get(
            "/purchase-orders",
            params={"date_from": "2026-09-20", "date_to": "2026-09-22"},
            headers=_HEADERS,
        )
        un_dia = client.get(
            "/purchase-orders",
            params={"date_from": "2026-09-25", "date_to": "2026-09-25"},
            headers=_HEADERS,
        )

    assert del_dia.status_code == 200
    assert [item["id"] for item in del_dia.json()["items"]] == [
        seeded_db["po_enviada"]
    ]
    # Rango inclusivo por fecha-sola: incluye el 20, 21 y 22.
    assert [item["id"] for item in rango.json()["items"]] == [
        seeded_db["po_enviada"],
        seeded_db["po_borrador"],
    ]
    # La fecha-sola de date_to cubre hasta el final del día (15:30 incluido).
    assert [item["id"] for item in un_dia.json()["items"]] == [
        seeded_db["po_borrador2"]
    ]


def test_get_lista_page_size_tope_100(seeded_db):
    with TestClient(app) as client:
        excedido = client.get(
            "/purchase-orders", params={"page_size": 101}, headers=_HEADERS
        )
    assert excedido.status_code == 422


def test_get_detalle_con_items_y_404(seeded_db):
    with TestClient(app) as client:
        response = client.get(
            f"/purchase-orders/{seeded_db['po_borrador']}", headers=_HEADERS
        )
        no_existe = client.get("/purchase-orders/999999", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == pytest.approx(seeded_db["po_borrador_total"])
    assert len(body["items"]) == 2
    for item in body["items"]:
        assert item["total"] == pytest.approx(item["quantity"] * item["unit_cost"])
    assert no_existe.status_code == 404


def test_patch_reemplaza_items_completos(seeded_db):
    order_id = seeded_db["po_borrador"]
    payload = {
        "expected_date": "2026-11-01T09:00:00",
        "items": [
            {"product_id": seeded_db["agotado"], "quantity": 5, "unit_cost": 1.0}
        ],
    }
    with TestClient(app) as client:
        response = client.patch(
            f"/purchase-orders/{order_id}", json=payload, headers=_HEADERS
        )
        detalle = client.get(f"/purchase-orders/{order_id}", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["expected_date"] == "2026-11-01T09:00:00"
    assert body["item_count"] == 1
    assert body["total"] == pytest.approx(5.0)
    assert [item["product_id"] for item in body["items"]] == [seeded_db["agotado"]]
    # El ítem antiguo (bajo) ya no está: fue reemplazo completo.
    assert [item["product_id"] for item in detalle.json()["items"]] == [
        seeded_db["agotado"]
    ]


def test_patch_solo_expected_date_conserva_items(seeded_db):
    order_id = seeded_db["po_borrador"]
    with TestClient(app) as client:
        response = client.patch(
            f"/purchase-orders/{order_id}",
            json={"expected_date": "2026-11-15T09:00:00"},
            headers=_HEADERS,
        )
    assert response.status_code == 200
    body = response.json()
    assert body["expected_date"] == "2026-11-15T09:00:00"
    assert body["item_count"] == 2
    assert body["total"] == pytest.approx(seeded_db["po_borrador_total"])


def test_patch_409_si_no_esta_en_borrador(seeded_db):
    with TestClient(app) as client:
        response = client.patch(
            f"/purchase-orders/{seeded_db['po_enviada']}",
            json={"expected_date": "2026-11-15T09:00:00"},
            headers=_HEADERS,
        )
    assert response.status_code == 409


def test_patch_404_si_no_existe(seeded_db):
    with TestClient(app) as client:
        response = client.patch(
            "/purchase-orders/999999",
            json={"expected_date": "2026-11-15T09:00:00"},
            headers=_HEADERS,
        )
    assert response.status_code == 404


def test_patch_422_duplicados(seeded_db):
    payload = {
        "items": [
            {"product_id": seeded_db["disponible"], "quantity": 1, "unit_cost": 1.0},
            {"product_id": seeded_db["disponible"], "quantity": 2, "unit_cost": 2.0},
        ]
    }
    with TestClient(app) as client:
        response = client.patch(
            f"/purchase-orders/{seeded_db['po_borrador']}",
            json=payload,
            headers=_HEADERS,
        )
    assert response.status_code == 422


def test_delete_204_solo_borrador(seeded_db):
    order_id = seeded_db["po_borrador2"]
    with TestClient(app) as client:
        response = client.delete(f"/purchase-orders/{order_id}", headers=_HEADERS)
        detalle = client.get(f"/purchase-orders/{order_id}", headers=_HEADERS)
        listado = client.get("/purchase-orders", headers=_HEADERS)

    assert response.status_code == 204
    assert detalle.status_code == 404
    assert listado.json()["total"] == seeded_db["total_ordenes"] - 1


def test_delete_409_enviada(seeded_db):
    with TestClient(app) as client:
        response = client.delete(
            f"/purchase-orders/{seeded_db['po_enviada']}", headers=_HEADERS
        )
    assert response.status_code == 409


def test_delete_404_si_no_existe(seeded_db):
    with TestClient(app) as client:
        response = client.delete("/purchase-orders/999999", headers=_HEADERS)
    assert response.status_code == 404


def test_post_patch_delete_empleado_403(seeded_db):
    payload = _payload(
        seeded_db,
        [{"product_id": seeded_db["disponible"], "quantity": 1, "unit_cost": 1.0}],
    )
    with TestClient(app) as client:
        post = client.post(
            "/purchase-orders", json=payload, headers=_EMPLOYEE_HEADERS
        )
        patch = client.patch(
            f"/purchase-orders/{seeded_db['po_borrador']}",
            json={"expected_date": "2026-11-15T09:00:00"},
            headers=_EMPLOYEE_HEADERS,
        )
        delete = client.delete(
            f"/purchase-orders/{seeded_db['po_borrador']}", headers=_EMPLOYEE_HEADERS
        )
    assert post.status_code == 403
    assert patch.status_code == 403
    assert delete.status_code == 403


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("get", "/purchase-orders"),
        ("get", "/purchase-orders/1"),
        ("post", "/purchase-orders"),
        ("patch", "/purchase-orders/1"),
        ("delete", "/purchase-orders/1"),
    ],
)
def test_sin_token_401(seeded_db, method, url):
    with TestClient(app) as client:
        response = getattr(client, method)(url)
    assert response.status_code == 401
