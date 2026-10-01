"""Cliente REST interno de Ventas hacia Inventario (F-004, paso 7).

Ventas reenvía el JWT del usuario al consultar el catálogo y al descontar stock
(ARCH §3). Los fallos de transporte (conexión/timeout) se traducen a
InventoryUnavailable para que el router responda 502; un 409 de Inventario se
traduce a InventoryConflict (no descontó nada).
"""

from collections.abc import Iterator

import httpx

from sales import config


class InventoryUnavailable(Exception):
    """Inventario no respondió o devolvió un estado inesperado."""


class InventoryConflict(Exception):
    """Inventario rechazó la operación con 409 (nada fue descontado)."""


class InventoryClient:
    def __init__(
        self,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=(base_url or config.INVENTORY_URL).rstrip("/"),
            transport=transport,
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _headers(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def get_products(self, product_ids: list[int], token: str) -> list[dict]:
        """GET /products?ids=... devolviendo las coincidencias (sin paginar)."""
        try:
            response = self._client.get(
                "/products",
                params={"ids": ",".join(str(i) for i in product_ids)},
                headers=self._headers(token),
            )
        except httpx.RequestError as exc:
            raise InventoryUnavailable(str(exc)) from exc
        if response.status_code != 200:
            raise InventoryUnavailable(f"Inventario respondió {response.status_code}")
        return response.json().get("items", [])

    def descontar_por_venta(
        self, reference: str, items: list[dict], token: str
    ) -> list[dict]:
        """POST /internal/movements/salida (lote atómico)."""
        try:
            response = self._client.post(
                "/internal/movements/salida",
                json={"reference": reference, "items": items},
                headers=self._headers(token),
            )
        except httpx.RequestError as exc:
            raise InventoryUnavailable(str(exc)) from exc
        if response.status_code == 409:
            raise InventoryConflict(response.text)
        if response.status_code != 200:
            raise InventoryUnavailable(f"Inventario respondió {response.status_code}")
        return response.json().get("items", [])

    def registrar_entrada_ajuste(
        self, product_id: int, quantity: int, reference: str, token: str
    ) -> None:
        """POST /movements (entrada, reason=ajuste) usado para compensar."""
        try:
            response = self._client.post(
                "/movements",
                json={
                    "product_id": product_id,
                    "movement_type": "entrada",
                    "quantity": quantity,
                    "reason": "ajuste",
                    "reference": reference,
                },
                headers=self._headers(token),
            )
        except httpx.RequestError as exc:
            raise InventoryUnavailable(str(exc)) from exc
        if response.status_code not in (200, 201):
            raise InventoryUnavailable(f"Inventario respondió {response.status_code}")


def get_inventory_client() -> Iterator[InventoryClient]:
    client = InventoryClient()
    try:
        yield client
    finally:
        client.close()
