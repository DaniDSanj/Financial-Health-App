"""App factory de FastAPI."""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

load_dotenv()

_TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def configure_proxy_headers(app: FastAPI, trusted_proxy_ips: list[str]) -> None:
    """Confía en X-Forwarded-Proto solo desde los orígenes de proxy indicados.

    Necesario para que `request.url.scheme` refleje HTTPS real cuando la app corre
    detrás de un proxy inverso/balanceador que termina TLS y reenvía por HTTP interno
    (ADR-0003). Sin orígenes de confianza configurados, la cabecera se ignora y el
    esquema se detecta tal cual llega la conexión (correcto cuando no hay proxy
    delante, p. ej. en desarrollo local).
    """
    if trusted_proxy_ips:
        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted_proxy_ips)


def create_app() -> FastAPI:
    app = FastAPI(title="Financial Health App")
    trusted_proxy_ips = [
        ip.strip()
        for ip in os.environ.get("TRUSTED_PROXY_IPS", "").split(",")
        if ip.strip()
    ]
    configure_proxy_headers(app, trusted_proxy_ips)

    # Import diferido: routers/login.py importa `templates` de este módulo, así que
    # se importa aquí (después de que `templates` ya esté definido arriba) para
    # evitar un ciclo de imports.
    from financial_health_app.routers.login import router as login_router

    app.include_router(login_router)
    return app


app = create_app()
