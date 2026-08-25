"""Test: fallo de BD durante el login devuelve error genérico, sin filtrar
detalle interno."""

from starlette.testclient import TestClient

from financial_health_app.db import get_db
from financial_health_app.main import app


class _BrokenSession:
    def execute(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, D102
        raise RuntimeError(
            "boom: fallo simulado de conexión a base de datos, ruta interna secreta"
        )

    def scalars(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, D102
        raise RuntimeError(
            "boom: fallo simulado de conexión a base de datos, ruta interna secreta"
        )


def test_db_failure_during_login_returns_generic_error_without_internal_details() -> (
    None
):
    app.dependency_overrides[get_db] = lambda: _BrokenSession()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/login", data={"identifier": "jdoe", "password": "Segura123!"}
        )
        assert response.status_code == 500
        assert "boom" not in response.text
        assert "RuntimeError" not in response.text
        assert "ruta interna secreta" not in response.text
        assert "Traceback" not in response.text
    finally:
        app.dependency_overrides.clear()
