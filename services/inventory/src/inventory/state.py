"""Cálculo del estado de stock (ARCH §7).

El estado no se almacena: se deriva en consulta de stock vs umbrales, por lo que
siempre es consistente tras editar los umbrales.
"""

AGOTADO = "agotado"
BAJO = "bajo"
DISPONIBLE = "disponible"
EXCESO = "exceso"

ESTADOS = (AGOTADO, BAJO, DISPONIBLE, EXCESO)


def compute_state(stock: int, min_threshold: int, excess_threshold: int) -> str:
    """Devuelve el semáforo de stock según ARCH §7."""
    if stock == 0:
        return AGOTADO
    if stock <= min_threshold:
        return BAJO
    if stock >= excess_threshold:
        return EXCESO
    return DISPONIBLE
