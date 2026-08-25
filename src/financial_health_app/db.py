"""Motor de base de datos y dependencia de sesión para FastAPI."""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()


class Base(DeclarativeBase):
    """Base declarativa de SQLAlchemy 2.0 para todos los modelos de la aplicación."""


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL no está definida en el entorno (.env)")
    return url


engine = create_engine(_database_url())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session]:
    """Dependencia de FastAPI: una sesión de BD por request, cerrada al finalizar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
