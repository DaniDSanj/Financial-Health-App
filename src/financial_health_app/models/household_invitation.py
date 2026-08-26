"""Código de invitación de un solo uso para asociarse a un hogar existente
(FR-006/FR-007)."""

from datetime import datetime

from sqlalchemy import (
    VARCHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from financial_health_app.db import Base


class HouseholdInvitation(Base):
    __tablename__ = "household_invitations"
    __table_args__ = (
        CheckConstraint(
            "(used_at IS NULL) = (used_by IS NULL)",
            name="ck_household_invitations_used_consistency",
        ),
        Index("ix_household_invitations_household_id", "household_id"),
        Index("ix_household_invitations_created_by", "created_by"),
        Index("ix_household_invitations_used_by", "used_by"),
        Index("ix_household_invitations_code_hash", "code_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("households.id"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    used_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
