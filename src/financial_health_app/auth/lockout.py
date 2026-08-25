"""Bloqueo anti-fuerza-bruta por usuario (FR-007): 5 fallos -> 15min, auto-reseteo."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from financial_health_app.models.user import User

_MAX_ATTEMPTS = 5
_LOCKOUT_DURATION = timedelta(minutes=15)


def check_lockout(user: User) -> bool:
    """True si el usuario tiene un bloqueo activo (locked_until en el futuro)."""
    if user.locked_until is None:
        return False
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=UTC)
    return locked_until > datetime.now(UTC)


def register_failed_attempt(db: Session, user: User) -> None:
    """Incrementa el contador de fallos y, al llegar a 5, fija locked_until.

    Patrón leer-incrementar-escribir con `SELECT ... FOR UPDATE`: necesario porque la
    decisión de bloquear depende de leer el valor actual antes de escribirlo (a
    diferencia de un incremento atómico de una sola sentencia, que Postgres ya
    serializa sin necesitar la cláusula) — ver tasks.md T034/T033 para el detalle de
    por qué esto importa bajo concurrencia. No hace commit — el llamador controla la
    transacción.
    """
    row = db.execute(
        select(User).where(User.id == user.id).with_for_update()
    ).scalar_one()
    row.failed_login_attempts += 1
    if row.failed_login_attempts >= _MAX_ATTEMPTS:
        row.locked_until = datetime.now(UTC) + _LOCKOUT_DURATION


def reset_lockout(user: User) -> None:
    """Resetea el contador y el bloqueo (login correcto, o auto-reseteo tras
    expirar)."""
    user.failed_login_attempts = 0
    user.locked_until = None
