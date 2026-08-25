"""Registro de auditoría de intentos de login (FR-012)."""

from typing import Literal

from sqlalchemy.orm import Session

from financial_health_app.models.login_audit_log import LoginAuditLog

LoginResult = Literal["success", "failure", "locked"]


def record_login_attempt(
    db: Session, *, user_id: int | None, identifier: str, result: LoginResult
) -> None:
    """Añade una fila a login_audit_log. No hace commit — el llamador controla la
    transacción."""
    db.add(
        LoginAuditLog(
            user_id=user_id,
            attempted_identifier=identifier,
            result=result,
        )
    )
