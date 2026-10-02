"""Cliente REST interno de Ventas hacia Inventario (F-004, paso 7).

Ventas reenvía el JWT del usuario al consultar el catálogo y al descontar stock
(ARCH §3). Los fallos de transporte (conexión/timeout) se traducen a
InventoryUnavailable para que el router responda 502; un 409 de Inventario se
traduce a InventoryConflict (no descontó nada).
"""

import threading
from collections.abc import Iterator

import httpx

from sales import config

_shared_client: httpx.Client | None = None
_shared_lock = threading.Lock()


def _get_shared_client() -> httpx.Client:
    """Devuelve el cliente HTTP compartido, creándolo de forma perezosa.

    Se reutiliza una única instancia para el camino por defecto (sin base_url
    ni transport inyectados) para aprovechar el pool de conexiones de httpx
    y evitar abrir una conexión nueva en cada request (en Windows resolver
    "localhost" cuesta ~2.5 s por llamada). httpx.Client es thread-safe y
    FastAPI ejecuta los endpoints sync en un threadpool.
    """
    global _shared_client
    if _shared_client is None:
        with _shared_lock:
            if _shared_client is None:
                _shared_client = httpx.Client(
                    base_url=config.INVENTORY_URL.rstrip("/"),
                    timeout=5.0,
                )
    return _shared_client


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
        if base_url is None and transport is None:
            # Camino por defecto: reutiliza el cliente compartido.
            self._client = _get_shared_client()
            self._owns_client = False
        else:
            # Cliente propio (tests con MockTransport, base_url explícita...).
            self._client = httpx.Client(
                base_url=(base_url or config.INVENTORY_URL).rstrip("/"),
                transport=transport,
                timeout=timeout,
            )
            self._owns_client = True

    def close(self) -> None:
        # No cerrar el cliente compartido: lo reutilizan otros requests.
        if self._owns_client:
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

    def get_products_page(
        self,
        token: str,
        page: int = 1,
        page_size: int = 50,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> dict:
        """GET /products paginado; devuelve el envelope {items, total, ...}.

        `category` e `is_active` se envían sólo si no son None. Pensado para
        recorrer todas las páginas (analítica/predicciones, F-005).
        """
        params: dict = {"page": page, "page_size": page_size}
        if category is not None:
            params["category"] = category
        if is_active is not None:
            params["is_active"] = is_active
        try:
            response = self._client.get(
                "/products", params=params, headers=self._headers(token)
            )
        except httpx.RequestError as exc:
            raise InventoryUnavailable(str(exc)) from exc
        if response.status_code != 200:
            raise InventoryUnavailable(f"Inventario respondió {response.status_code}")
        return response.json()

    def get_all_purchase_orders(
        self, token: str, page_size: int = 100
    ) -> list[dict]:
        """Recorre GET /purchase-orders (page_size=100) y devuelve todas.

        Sin filtros de fecha: el filtro por `received_at` se aplica localmente
        en sales (F-005, purchases-summary).
        """
        orders: list[dict] = []
        page = 1
        while True:
            try:
                response = self._client.get(
                    "/purchase-orders",
                    params={"page": page, "page_size": page_size},
                    headers=self._headers(token),
                )
            except httpx.RequestError as exc:
                raise InventoryUnavailable(str(exc)) from exc
            if response.status_code != 200:
                raise InventoryUnavailable(
                    f"Inventario respondió {response.status_code}"
                )
            items = response.json().get("items", [])
            orders.extend(items)
            if len(items) < page_size:
                break
            page += 1
        return orders

    def get_suppliers(self, token: str) -> list[dict]:
        """GET /suppliers y devuelve la lista completa."""
        try:
            response = self._client.get(
                "/suppliers", headers=self._headers(token)
            )
        except httpx.RequestError as exc:
            raise InventoryUnavailable(str(exc)) from exc
        if response.status_code != 200:
            raise InventoryUnavailable(f"Inventario respondió {response.status_code}")
        return response.json()

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
