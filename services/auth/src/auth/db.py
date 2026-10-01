import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from auth import config


def get_engine() -> Engine:
    # Se lee la variable de entorno en cada llamada para que los tests
    # puedan redirigir la BD a un fichero temporal.
    path = os.getenv("AUTH_DB", config.DB_PATH)
    return create_engine(f"sqlite:///{path}", echo=False)


def get_session_factory(engine: Engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
