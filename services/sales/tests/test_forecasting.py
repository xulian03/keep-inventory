"""Tests unitarios del modelo de predicción (F-005, paso 1).

Sólo `sales.forecasting`: regresión vs media móvil, tendencia, formato de las
salidas y fórmulas de fecha_agotamiento/demanda_30d/reorden_sugerido.
"""

from datetime import date

import pytest
from sales.forecasting import predict_demand

HOY = date(2026, 5, 1)


def test_serie_creciente_usa_regresion_y_tendencia_subiendo():
    serie = list(range(1, 21))  # 20 días, todos con ventas, pendiente m=1

    resultado = predict_demand(serie, stock=50, min_threshold=5, hoy=HOY)

    assert resultado.method == "regresion"
    assert resultado.trend == "subiendo"
    assert resultado.daily_demand > sum(serie) / len(serie)
    assert resultado.daily_demand == pytest.approx(35.5)


def test_serie_plana_es_estable():
    serie = [5] * 30

    resultado = predict_demand(serie, stock=20, min_threshold=5, hoy=HOY)

    assert resultado.method == "regresion"
    assert resultado.trend == "estable"
    assert resultado.daily_demand == 5.0


def test_serie_decreciente_aplica_clamp_a_cero():
    serie = list(range(30, 0, -1))  # pendiente negativa: proyección negativa

    resultado = predict_demand(serie, stock=10, min_threshold=5, hoy=HOY)

    assert resultado.method == "regresion"
    assert resultado.trend == "bajando"
    assert resultado.daily_demand == 0.0
    assert resultado.stockout_date is None
    assert resultado.demand_30d == 0
    assert resultado.suggested_reorder == max(0, 5 - 10)


def test_menos_de_diez_dias_con_ventas_usa_media_movil():
    serie = [0] * 118 + [3, 3]  # sólo 2 días con ventas

    resultado = predict_demand(serie, stock=10, min_threshold=5, hoy=HOY)

    assert resultado.method == "media_movil"
    assert resultado.trend == "estable"
    # media de los últimos 30 días: (28 ceros + 3 + 3) / 30
    assert resultado.daily_demand == pytest.approx(0.2)


def test_serie_corta_usa_toda_la_serie():
    serie = [1, 1, 1, 1, 1]  # n=5 < 30

    resultado = predict_demand(serie, stock=10, min_threshold=5, hoy=HOY)

    assert resultado.method == "media_movil"
    assert resultado.daily_demand == 1.0


def test_serie_vacia_de_ventas_demanda_cero():
    serie = [0] * 120

    resultado = predict_demand(serie, stock=4, min_threshold=10, hoy=HOY)

    assert resultado.daily_demand == 0.0
    assert resultado.method == "media_movil"
    assert resultado.trend == "estable"
    assert resultado.stockout_date is None
    assert resultado.demand_30d == 0
    assert resultado.suggested_reorder == max(0, 10 - 4)


def test_formulas_con_valores_calculados_a_mano():
    serie = [2] * 30  # demanda_diaria = 2.0

    resultado = predict_demand(serie, stock=10, min_threshold=5, hoy=HOY)

    assert resultado.daily_demand == 2.0
    assert resultado.demand_30d == 60
    assert resultado.suggested_reorder == max(0, 60 + 5 - 10)
    assert resultado.stockout_date == HOY.replace(day=6)  # +5 días


def test_reorden_nunca_negativo_si_hay_stock_suficiente():
    serie = [1] * 30

    resultado = predict_demand(serie, stock=100, min_threshold=5, hoy=HOY)

    assert resultado.suggested_reorder == 0
