"""Test de integración: detección de HTTPS vía X-Forwarded-Proto desde un proxy
de confianza."""

from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from financial_health_app.main import configure_proxy_headers


def _build_app() -> FastAPI:
    """App de prueba desechable con la misma configuración de proxy que main.py."""
    app = FastAPI()
    configure_proxy_headers(app, trusted_proxy_ips=["127.0.0.1"])

    @app.get("/_scheme")
    async def scheme_probe(request: Request) -> dict:
        return {"scheme": request.url.scheme}

    return app


def test_https_scheme_detected_from_trusted_proxy_header() -> None:
    app = _build_app()
    client = TestClient(app, client=("127.0.0.1", 12345))

    response = client.get("/_scheme", headers={"X-Forwarded-Proto": "https"})

    assert response.json() == {"scheme": "https"}


def test_scheme_stays_http_without_forwarded_header() -> None:
    app = _build_app()
    client = TestClient(app, client=("127.0.0.1", 12345))

    response = client.get("/_scheme")

    assert response.json() == {"scheme": "http"}
