"""Bloqueo anti-fuerza-bruta de códigos de invitación por usuario (FR-013),
mismo patrón que auth/lockout.py de 001."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from financial_health_app.models.user import User

_MAX_ATTEMPTS = 5
_LOCKOUT_DURATION = timedelta(minutes=15)


def check_invite_lockout(user: User) -> bool:
    """True si el usuario tiene un bloqueo activo (invite_locked_until en el
    futuro)."""
    if user.invite_locked_until is None:
        return False
    locked_until = user.invite_locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=UTC)
    return locked_until > datetime.now(UTC)


def register_failed_invite_attempt(db: Session, user: User) -> None:
    """Incrementa el contador de fallos y, al llegar a 5, fija
    invite_locked_until. Patrón leer-incrementar-escribir con
    `SELECT ... FOR UPDATE` — mismo motivo que auth/lockout.py de 001. No hace
    commit — el llamador controla la transacción."""
    row = db.execute(
        select(User).where(User.id == user.id).with_for_update()
    ).scalar_one()
    row.failed_invite_attempts += 1
    if row.failed_invite_attempts >= _MAX_ATTEMPTS:
        row.invite_locked_until = datetime.now(UTC) + _LOCKOUT_DURATION


def reset_invite_lockout(user: User) -> None:
    """Resetea el contador y el bloqueo (join correcto, o auto-reseteo tras
    expirar)."""
    user.failed_invite_attempts = 0
    user.invite_locked_until = None
