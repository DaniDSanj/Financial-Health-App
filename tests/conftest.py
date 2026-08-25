"""Fixtures compartidas de pytest: bootstrap de BD de test, sesión con rollback,
motor crudo."""

import os
from collections.abc import Generator

import pytest
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from alembic import command

load_dotenv()

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError("TEST_DATABASE_URL no está definida en el entorno (.env)")
    return url


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_database() -> None:
    """Aplica las migraciones Alembic contra TEST_DATABASE_URL, una vez por sesión.

    Sobrescribe explícitamente sqlalchemy.url para que env.py migre la base de
    datos de TEST_DATABASE_URL y nunca la de DATABASE_URL (desarrollo) por defecto
    de configuración.
    """
    cfg = Config(os.path.join(_REPO_ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_REPO_ROOT, "alembic"))
    # configparser interpreta "%" como carácter de interpolación: escapar como "%%"
    # (la URL puede llevar una contraseña URL-encoded con "%").
    cfg.set_main_option("sqlalchemy.url", _test_database_url().replace("%", "%%"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def _test_engine(_migrate_test_database: None) -> Engine:
    return create_engine(_test_database_url())


@pytest.fixture
def db_session(_test_engine: Engine) -> Generator[Session]:
    """Sesión de test con rollback tras cada test (savepoint sobre una conexión).

    NO usar para tests de concurrencia real (ver fixture db_engine) — todas las
    operaciones de un test comparten esta misma conexión/transacción física, así
    que dos "sesiones" contra este fixture nunca contienden de verdad por un lock
    (research.md §5).
    """
    connection = _test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(
        bind=connection, autoflush=False, expire_on_commit=False
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def db_engine(_migrate_test_database: None) -> Engine:
    """Motor SQLAlchemy crudo, sin la transacción compartida de db_session.

    Para tests que necesitan conexiones genuinamente independientes (p. ej. T033,
    concurrencia real del lockout). Quien use este fixture es responsable de
    limpiar sus propios datos de test explícitamente — no hay rollback automático.
    """
    return create_engine(_test_database_url())


@pytest.fixture
def client(db_session: Session):
    """TestClient de FastAPI con get_db sobrescrito hacia la sesión de test
    (rollback)."""
    from starlette.testclient import TestClient

    from financial_health_app.db import get_db
    from financial_health_app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
