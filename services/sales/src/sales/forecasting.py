"""Modelo de predicción de demanda (F-005, paso 1; ARCHITECTURE §8).

Módulo puro: sin base de datos, sin FastAPI y sin httpx. Sólo sklearn y stdlib.
Recibe la serie diaria de unidades (ceros incluidos, hasta 120 días), el stock,
el umbral mínimo y la fecha de hoy, y estima la demanda diaria por producto.

Con >=10 días con ventas se ajusta una regresión lineal y = m·d + b (d=0..n-1)
y se proyectan los 30 días siguientes. En caso contrario se usa la media móvil
simple de los últimos 30 días de la serie. Ver spec F-005 §Modelo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sklearn.linear_model import LinearRegression

DIAS_MINIMOS_REGRESION = 10
DIAS_PROYECCION = 30
UMBRAL_TENDENCIA = 0.05


@dataclass(frozen=True)
class Forecast:
    """Resultado del modelo para un producto (F-005, ARCHITECTURE §8)."""

    daily_demand: float
    trend: str
    method: str
    stockout_date: date | None
    demand_30d: int
    suggested_reorder: int


def _regresion(serie: list[int]) -> tuple[float, str]:
    """Ajusta y=m·d+b y devuelve (demanda_diaria proyectada, tendencia)."""
    n = len(serie)
    x = [[d] for d in range(n)]
    modelo = LinearRegression().fit(x, serie)
    m = float(modelo.coef_[0])

    predicciones = modelo.predict([[d] for d in range(n, n + DIAS_PROYECCION)])
    demanda = max(0.0, sum(float(p) for p in predicciones) / DIAS_PROYECCION)

    media_historica = sum(serie) / n
    if abs(m) * DIAS_PROYECCION <= UMBRAL_TENDENCIA * media_historica:
        trend = "estable"
    elif m > 0:
        trend = "subiendo"
    else:
        trend = "bajando"
    return demanda, trend


def _media_movil(serie: list[int]) -> float:
    """Media simple de los últimos 30 días (toda la serie si es más corta)."""
    if not serie:
        return 0.0
    ultimos = serie[-DIAS_PROYECCION:]
    return sum(ultimos) / len(ultimos)


def predict_demand(
    serie: list[int],
    stock: int,
    min_threshold: int,
    hoy: date,
) -> Forecast:
    """Predice la demanda de un producto a partir de su serie diaria.

    `serie` es la lista de unidades vendidas por día con ceros incluidos (hasta
    120 días). Devuelve el resultado del modelo descrito en F-005 §Modelo.
    """
    dias_con_ventas = sum(1 for valor in serie if valor >= 1)

    if len(serie) >= DIAS_MINIMOS_REGRESION and dias_con_ventas >= DIAS_MINIMOS_REGRESION:
        demanda, trend = _regresion(serie)
        method = "regresion"
    else:
        demanda, trend = _media_movil(serie), "estable"
        method = "media_movil"

    daily_demand = round(max(0.0, demanda), 2)
    demand_30d = round(daily_demand * DIAS_PROYECCION)
    suggested_reorder = max(
        0, round(demand_30d + min_threshold - stock)
    )
    if daily_demand > 0:
        stockout_date = hoy + timedelta(days=stock / daily_demand)
    else:
        stockout_date = None

    return Forecast(
        daily_demand=daily_demand,
        trend=trend,
        method=method,
        stockout_date=stockout_date,
        demand_30d=demand_30d,
        suggested_reorder=suggested_reorder,
    )
