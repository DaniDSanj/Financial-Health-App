"""App factory de FastAPI."""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

load_dotenv()


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
    from financial_health_app.routers.household import router as household_router
    from financial_health_app.routers.login import router as login_router
    from financial_health_app.routers.register import router as register_router

    app.include_router(login_router)
    app.include_router(register_router)
    app.include_router(household_router)
    return app


app = create_app()
