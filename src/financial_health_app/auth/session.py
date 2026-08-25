"""Gestión de sesión de servidor: creación (UPSERT), validación y logout (FR-004)."""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from financial_health_app.models.user import User
from financial_health_app.models.user_session import UserSession

_SESSION_WINDOW = timedelta(hours=24)


def create_session(db: Session, user_id: int) -> str:
    """Crea (UPSERT) la sesión del usuario, invalidando cualquier sesión anterior
    (FR-004)."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + _SESSION_WINDOW
    stmt = insert(UserSession).values(
        user_id=user_id, session_token=token, expires_at=expires_at
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserSession.user_id],
        set_={
            "session_token": token,
            "expires_at": expires_at,
            "updated_at": datetime.now(UTC),
        },
    )
    db.execute(stmt)
    return token


def validate_session(db: Session, session_token: str) -> User | None:
    """Devuelve el usuario de una sesión válida (token existe, no expirada),
    deslizando su expiración (ventana de 24h de inactividad — spec Clarifications
    2026-08-25). None si no hay sesión válida.
    """
    session_row = (
        db.query(UserSession).filter(UserSession.session_token == session_token).first()
    )
    if session_row is None:
        return None
    now = datetime.now(UTC)
    expires_at = session_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < now:
        return None

    session_row.expires_at = now + _SESSION_WINDOW
    db.commit()

    return db.get(User, session_row.user_id)


def invalidate_session(db: Session, session_token: str) -> None:
    db.execute(delete(UserSession).where(UserSession.session_token == session_token))
    db.commit()
