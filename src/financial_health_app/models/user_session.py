"""Sesión de servidor única por usuario (PK = user_id, UPSERT en cada login)."""

from datetime import datetime

from sqlalchemy import VARCHAR, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from financial_health_app.db import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    session_token: Mapped[str] = mapped_column(
        VARCHAR(255), nullable=False, unique=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
