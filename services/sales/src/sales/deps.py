from collections.abc import Iterator
from datetime import datetime, time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from sales import db as db_module


def get_session() -> Iterator[Session]:
    engine = db_module.get_engine()
    session = db_module.get_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()


def parse_date_bound(value: str | None, *, end: bool) -> str | None:
    """Normaliza un filtro de fecha a ISO-8601 con separador 'T'.

    Si llega sólo la fecha (YYYY-MM-DD) se expande al inicio del día o al final
    (23:59:59.999999) según `end`; si llega un datetime completo se usa tal cual.
    """
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="Fecha inválida")
    if "T" not in value and " " not in value:
        if end:
            parsed = datetime.combine(parsed.date(), time.max)
        else:
            parsed = datetime.combine(parsed.date(), time.min)
    return parsed.replace(tzinfo=None).isoformat()
