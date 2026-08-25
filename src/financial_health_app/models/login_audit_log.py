"""Registro de auditoría de intentos de login (append-only, retención 90 días)."""

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


class LoginAuditLog(Base):
    __tablename__ = "login_audit_log"
    __table_args__ = (
        CheckConstraint(
            "result IN ('success', 'failure', 'locked')",
            name="ck_login_audit_log_result",
        ),
        Index("ix_login_audit_log_occurred_at", "occurred_at", postgresql_using="brin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    attempted_identifier: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    result: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
