"""Registro de auditoría de intentos de código de invitación (FR-015)."""

from typing import Literal

from sqlalchemy.orm import Session

from financial_health_app.models.household_invitation_attempt_log import (
    HouseholdInvitationAttemptLog,
)

InviteAttemptResult = Literal["success", "failure", "locked"]


def record_invite_attempt(
    db: Session, *, user_id: int, household_id: int | None, result: InviteAttemptResult
) -> None:
    """Añade una fila a household_invitation_attempts_log. No hace commit — el
    llamador controla la transacción."""
    db.add(
        HouseholdInvitationAttemptLog(
            user_id=user_id,
            household_id=household_id,
            result=result,
        )
    )
