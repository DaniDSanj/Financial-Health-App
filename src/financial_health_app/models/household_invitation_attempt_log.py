"""Registro de auditoría de cada intento de introducir un código de invitación
(append-only, retención 90 días) — FR-015, simétrico a login_audit_log de 001."""

from datetime import datetime

from sqlalchemy import (
    VARCHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from financial_health_app.db import Base


class HouseholdInvitationAttemptLog(Base):
    __tablename__ = "household_invitation_attempts_log"
    __table_args__ = (
        CheckConstraint(
            "result IN ('success', 'failure', 'locked')",
            name="ck_household_invitation_attempts_log_result",
        ),
        Index("ix_household_invitation_attempts_log_user_id", "user_id"),
        Index("ix_household_invitation_attempts_log_household_id", "household_id"),
        Index(
            "ix_household_invitation_attempts_log_occurred_at",
            "occurred_at",
            postgresql_using="brin",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    household_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("households.id"), nullable=True
    )
    result: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
