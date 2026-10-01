"""Tests del catálogo de inventario (F-004, pasos 1 y 2).

La fixture seeded_db (BD temporal) vive en conftest.py.
"""

import pytest
from fastapi.testclient import TestClient
from inventory import rbac
from inventory.main import app

_HEADERS = {"Authorization": f"Bearer {rbac.create_access_token(1, 'admin', 'Admin')}"}
_EMPLOYEE_HEADERS = {
    "Authorization": f"Bearer {rbac.create_access_token(2, 'empleado', 'Empleado')}"
}


def test_list_default_page_size_y_orden(seeded_db):
    with TestClient(app) as client:
        response = client.get("/products", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 50
    assert body["total"] == seeded_db["total_productos"]
    assert len(body["items"]) == 50
    returned_ids = [item["id"] for item in body["items"]]
    assert returned_ids == sorted(returned_ids)


def test_list_segunda_pagina(seeded_db):
    with TestClient(app) as client:
        response = client.get(
            "/products", params={"page": 2, "page_size": 50}, headers=_HEADERS
        )

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 2
    assert len(body["items"]) == seeded_db["total_productos"] - 50


def test_page_size_tope_100(seeded_db):
    with TestClient(app) as client:
        excedido = client.get(
            "/products", params={"page_size": 101}, headers=_HEADERS
        )
        permitido = client.get(
            "/products", params={"page_size": 100}, headers=_HEADERS
        )

    assert excedido.status_code == 422
    assert permitido.status_code == 200
    assert permitido.json()["page_size"] == 100


def test_filtro_search_por_nombre(seeded_db):
    with TestClient(app) as client:
        response = client.get(
            "/products", params={"search": "aceite"}, headers=_HEADERS
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Aceite Exceso"


def test_filtro_search_por_marca(seeded_db):
    with TestClient(app) as client:
        response = client.get(
            "/products", params={"search": "MarcaA"}, headers=_HEADERS
        )

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_filtro_category(seeded_db):
    with TestClient(app) as client:
        response = client.get(
            "/products", params={"category": "Lacteos"}, headers=_HEADERS
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == seeded_db["bajo"]


def test_filtro_is_active(seeded_db):
    with TestClient(app) as client:
        inactivos = client.get(
            "/products", params={"is_active": "false"}, headers=_HEADERS
        )
        activos = client.get(
            "/products", params={"is_active": "true"}, headers=_HEADERS
        )

    assert inactivos.status_code == 200
    assert inactivos.json()["total"] == 1
    assert inactivos.json()["items"][0]["id"] == seeded_db["inactivo"]
    assert activos.status_code == 200
    assert activos.json()["total"] == seeded_db["total_productos"] - 1


def test_filtro_state(seeded_db):
    with TestClient(app) as client:
        response = client.get(
            "/products", params={"state": "agotado"}, headers=_HEADERS
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == seeded_db["agotado"]
    assert all(item["state"] == "agotado" for item in body["items"])


def test_ids_ignora_paginacion(seeded_db):
    ids = f"{seeded_db['agotado']},{seeded_db['exceso']}"
    with TestClient(app) as client:
        response = client.get(
            "/products",
            params={"ids": ids, "page": 5, "page_size": 1},
            headers=_HEADERS,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    assert {item["id"] for item in body["items"]} == {
        seeded_db["agotado"],
        seeded_db["exceso"],
    }


def test_detalle_state_y_supplier_name(seeded_db):
    with TestClient(app) as client:
        con_proveedor = client.get(
            f"/products/{seeded_db['bajo']}", headers=_HEADERS
        )
        sin_proveedor = client.get(
            f"/products/{seeded_db['disponible']}", headers=_HEADERS
        )

    assert con_proveedor.status_code == 200
    assert con_proveedor.json()["state"] == "bajo"
    assert con_proveedor.json()["supplier_name"] == "Proveedor Uno"
    assert sin_proveedor.status_code == 200
    assert sin_proveedor.json()["supplier_name"] is None


@pytest.mark.parametrize(
    ("product_key", "expected_state"),
    [
        ("agotado", "agotado"),
        ("bajo", "bajo"),
        ("disponible", "disponible"),
        ("exceso", "exceso"),
    ],
)
def test_state_calculo_cuatro_estados(seeded_db, product_key, expected_state):
    with TestClient(app) as client:
        response = client.get(
            f"/products/{seeded_db[product_key]}", headers=_HEADERS
        )

    assert response.status_code == 200
    assert response.json()["state"] == expected_state


def test_detalle_404(seeded_db):
    with TestClient(app) as client:
        response = client.get("/products/999999", headers=_HEADERS)
    assert response.status_code == 404


@pytest.mark.parametrize("url", ["/products", "/products/1", "/categories"])
def test_sin_token_401(seeded_db, url):
    with TestClient(app) as client:
        response = client.get(url)
    assert response.status_code == 401


def test_categories(seeded_db):
    with TestClient(app) as client:
        response = client.get("/categories", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert "Alimentos" in body["categories"]
    assert "Relleno" in body["categories"]
    assert "Leche" in body["subcategories"]


# --- F-004 paso 2: PATCH productos/umbral, suppliers y alerts ---


def test_patch_product_parcial_solo_cambia_lo_enviado(seeded_db):
    product_id = seeded_db["disponible"]
    with TestClient(app) as client:
        response = client.patch(
            f"/products/{product_id}",
            json={"name": "Pan Editado", "sale_price": 9.5},
            headers=_HEADERS,
        )
        detalle = client.get(f"/products/{product_id}", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Pan Editado"
    assert body["sale_price"] == 9.5
    # Campos no enviados permanecen intactos.
    assert body["market_price"] == 2.0
    assert body["is_active"] is True
    assert body["stock"] == 50
    assert body["state"] == "disponible"
    assert detalle.json()["name"] == "Pan Editado"


def test_patch_product_is_active(seeded_db):
    product_id = seeded_db["disponible"]
    with TestClient(app) as client:
        response = client.patch(
            f"/products/{product_id}", json={"is_active": False}, headers=_HEADERS
        )

    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is False
    assert body["name"] == "Pan Disponible"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"sale_price": 0},
        {"sale_price": -1.5},
        {"market_price": -0.1},
    ],
)
def test_patch_product_validaciones_422(seeded_db, payload):
    with TestClient(app) as client:
        response = client.patch(
            f"/products/{seeded_db['disponible']}", json=payload, headers=_HEADERS
        )
    assert response.status_code == 422


def test_patch_threshold_422_inconsistente(seeded_db):
    with TestClient(app) as client:
        response = client.patch(
            f"/products/{seeded_db['disponible']}/threshold",
            json={"min_threshold": 200, "excess_threshold": 100},
            headers=_HEADERS,
        )
    assert response.status_code == 422


def test_patch_threshold_422_min_negativo(seeded_db):
    with TestClient(app) as client:
        response = client.patch(
            f"/products/{seeded_db['disponible']}/threshold",
            json={"min_threshold": -1},
            headers=_HEADERS,
        )
    assert response.status_code == 422


def test_patch_threshold_recalcula_state(seeded_db):
    product_id = seeded_db["disponible"]
    with TestClient(app) as client:
        response = client.patch(
            f"/products/{product_id}/threshold",
            json={"min_threshold": 60},
            headers=_HEADERS,
        )
        detalle = client.get(f"/products/{product_id}", headers=_HEADERS)

    assert response.status_code == 200
    assert response.json()["min_threshold"] == 60
    assert response.json()["excess_threshold"] == 100
    # stock 50 <= min 60 deja de estar disponible y pasa a bajo.
    assert response.json()["state"] == "bajo"
    assert detalle.json()["state"] == "bajo"


def test_patch_empleado_403(seeded_db):
    with TestClient(app) as client:
        producto = client.patch(
            f"/products/{seeded_db['disponible']}",
            json={"name": "No permitido"},
            headers=_EMPLOYEE_HEADERS,
        )
        umbral = client.patch(
            f"/products/{seeded_db['disponible']}/threshold",
            json={"min_threshold": 1},
            headers=_EMPLOYEE_HEADERS,
        )
    assert producto.status_code == 403
    assert umbral.status_code == 403


@pytest.mark.parametrize(
    "url",
    ["/products/999999", "/products/999999/threshold"],
)
def test_patch_404(seeded_db, url):
    with TestClient(app) as client:
        response = client.patch(url, json={}, headers=_HEADERS)
    assert response.status_code == 404


def test_suppliers_lista_completa(seeded_db):
    with TestClient(app) as client:
        response = client.get("/suppliers", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Proveedor Uno"
    assert body[0]["contact_email"] == "uno@test.com"
    assert body[0]["lead_time_days"] == 3


def test_alerts_agotados_primero_y_sin_disponibles(seeded_db):
    with TestClient(app) as client:
        response = client.get("/alerts", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [
        seeded_db["agotado"],
        seeded_db["bajo"],
    ]
    assert [item["state"] for item in body["items"]] == ["agotado", "bajo"]
    assert body["page"] == 1
    assert body["page_size"] == 50


def test_alerts_paginado_y_tope_page_size(seeded_db):
    with TestClient(app) as client:
        primera = client.get(
            "/alerts", params={"page": 1, "page_size": 1}, headers=_HEADERS
        )
        segunda = client.get(
            "/alerts", params={"page": 2, "page_size": 1}, headers=_HEADERS
        )
        excedido = client.get(
            "/alerts", params={"page_size": 101}, headers=_HEADERS
        )

    assert primera.status_code == 200
    body = primera.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == seeded_db["agotado"]
    assert segunda.json()["items"][0]["id"] == seeded_db["bajo"]
    assert excedido.status_code == 422


@pytest.mark.parametrize("url", ["/suppliers", "/alerts"])
def test_suppliers_alerts_sin_token_401(seeded_db, url):
    with TestClient(app) as client:
        response = client.get(url)
    assert response.status_code == 401


# --- F-004 paso 3: GET /movements + POST /movements ---


def test_movements_envelope_y_orden_desc(seeded_db):
    with TestClient(app) as client:
        response = client.get("/movements", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 50
    assert body["total"] == seeded_db["total_movimientos"]
    fechas = [item["created_at"] for item in body["items"]]
    assert fechas == sorted(fechas, reverse=True)
    # 2026-09-28, 2026-09-25, 2026-09-22, 2026-09-20.
    assert fechas == [
        "2026-09-28T09:15:00",
        "2026-09-25T15:30:00",
        "2026-09-22T08:00:00",
        "2026-09-20T10:00:00",
    ]


def test_movements_page_size_tope_100(seeded_db):
    with TestClient(app) as client:
        excedido = client.get(
            "/movements", params={"page_size": 101}, headers=_HEADERS
        )
        permitido = client.get(
            "/movements", params={"page_size": 100}, headers=_HEADERS
        )

    assert excedido.status_code == 422
    assert permitido.status_code == 200
    assert permitido.json()["page_size"] == 100


def test_movements_filtro_movement_type_y_reason(seeded_db):
    with TestClient(app) as client:
        salidas = client.get(
            "/movements", params={"movement_type": "salida"}, headers=_HEADERS
        )
        ajustes = client.get(
            "/movements", params={"reason": "ajuste"}, headers=_HEADERS
        )

    assert salidas.status_code == 200
    assert salidas.json()["total"] == 1
    assert salidas.json()["items"][0]["reason"] == "venta"
    assert ajustes.status_code == 200
    assert ajustes.json()["total"] == 2
    assert all(item["reason"] == "ajuste" for item in ajustes.json()["items"])


def test_movements_filtro_combinado_producto_y_fechas(seeded_db):
    product_id = seeded_db["disponible"]
    with TestClient(app) as client:
        response = client.get(
            "/movements",
            params={
                "product_id": product_id,
                "date_from": "2026-09-24T00:00:00",
                "date_to": "2026-09-26T23:59:59",
            },
            headers=_HEADERS,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["movement_type"] == "salida"
    assert body["items"][0]["product_id"] == product_id


def test_post_entrada_suma_stock_y_crea_movimiento(seeded_db):
    product_id = seeded_db["disponible"]
    with TestClient(app) as client:
        response = client.post(
            "/movements",
            json={
                "product_id": product_id,
                "movement_type": "entrada",
                "quantity": 10,
                "reason": "compra",
                "reference": "po:99",
            },
            headers=_HEADERS,
        )
        detalle = client.get(f"/products/{product_id}", headers=_HEADERS)
        listado = client.get(
            "/movements", params={"product_id": product_id}, headers=_HEADERS
        )

    assert response.status_code == 201
    body = response.json()
    assert body["stock"] == 60
    movement = body["movement"]
    assert movement["product_id"] == product_id
    assert movement["movement_type"] == "entrada"
    assert movement["quantity"] == 10
    assert movement["reason"] == "compra"
    assert movement["reference"] == "po:99"
    assert detalle.json()["stock"] == 60
    assert listado.json()["total"] == seeded_db["movimientos_disponible"] + 1
    assert listado.json()["items"][0]["id"] == movement["id"]


def test_post_salida_resta_stock(seeded_db):
    product_id = seeded_db["disponible"]
    with TestClient(app) as client:
        response = client.post(
            "/movements",
            json={
                "product_id": product_id,
                "movement_type": "salida",
                "quantity": 20,
                "reason": "ajuste",
            },
            headers=_HEADERS,
        )
        detalle = client.get(f"/products/{product_id}", headers=_HEADERS)

    assert response.status_code == 201
    assert response.json()["stock"] == 30
    assert response.json()["movement"]["reference"] is None
    assert detalle.json()["stock"] == 30


def test_post_salida_409_sin_cambios(seeded_db):
    product_id = seeded_db["bajo"]
    with TestClient(app) as client:
        antes = client.get(
            "/movements", params={"product_id": product_id}, headers=_HEADERS
        )
        response = client.post(
            "/movements",
            json={
                "product_id": product_id,
                "movement_type": "salida",
                "quantity": 999,
                "reason": "ajuste",
            },
            headers=_HEADERS,
        )
        des_ = client.get(f"/products/{product_id}", headers=_HEADERS)
        despues = client.get(
            "/movements", params={"product_id": product_id}, headers=_HEADERS
        )

    assert response.status_code == 409
    assert des_.json()["stock"] == 5
    assert despues.json()["total"] == antes.json()["total"]


@pytest.mark.parametrize(
    ("movement_type", "quantity", "reason"),
    [
        ("entrada", 0, "compra"),
        ("entrada", -3, "compra"),
        ("transferencia", 5, "ajuste"),
        ("entrada", 5, "venta"),
        ("entrada", 5, "otro"),
    ],
)
def test_post_movement_validaciones_422(
    seeded_db, movement_type, quantity, reason
):
    with TestClient(app) as client:
        response = client.post(
            "/movements",
            json={
                "product_id": seeded_db["disponible"],
                "movement_type": movement_type,
                "quantity": quantity,
                "reason": reason,
            },
            headers=_HEADERS,
        )
    assert response.status_code == 422


def test_post_movement_404_producto(seeded_db):
    with TestClient(app) as client:
        response = client.post(
            "/movements",
            json={
                "product_id": 999999,
                "movement_type": "entrada",
                "quantity": 5,
                "reason": "compra",
            },
            headers=_HEADERS,
        )
    assert response.status_code == 404


def test_post_movement_empleado_puede_crear(seeded_db):
    product_id = seeded_db["disponible"]
    with TestClient(app) as client:
        response = client.post(
            "/movements",
            json={
                "product_id": product_id,
                "movement_type": "entrada",
                "quantity": 7,
                "reason": "ajuste",
            },
            headers=_EMPLOYEE_HEADERS,
        )

    assert response.status_code == 201
    assert response.json()["stock"] == 57


@pytest.mark.parametrize("url", ["/movements"])
def test_movements_sin_token_401(seeded_db, url):
    with TestClient(app) as client:
        response = client.get(url)
    assert response.status_code == 401


def test_post_movement_sin_token_401(seeded_db):
    with TestClient(app) as client:
        response = client.post(
            "/movements",
            json={
                "product_id": seeded_db["disponible"],
                "movement_type": "entrada",
                "quantity": 5,
                "reason": "compra",
            },
        )
    assert response.status_code == 401
