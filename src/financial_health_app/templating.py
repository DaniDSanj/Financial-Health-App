"""Instancia compartida de Jinja2Templates.

Vive en su propio módulo (no en main.py) para que los routers puedan importarla
sin depender de que `financial_health_app.main` ya esté completamente inicializado
— main.py importa los routers de forma diferida dentro de `create_app()`, pero un
test que importe un router directamente (p. ej. para probar su lógica de negocio
sin pasar por la app completa) sí puede disparar el ciclo si `templates` sigue
viviendo en main.py.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
