"""Usuario de la plataforma (login, hash de contraseña, contador de bloqueo)."""

from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    VARCHAR,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from financial_health_app.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        ForeignKeyConstraint(
            ["permission_level_group", "permission_level_code"],
            ["keys_catalog.group_code", "keys_catalog.code"],
            name="fk_users_permission_level",
        ),
        Index("ix_users_username_lower", text("lower(username)"), unique=True),
        Index("ix_users_email_lower", text("lower(email)"), unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(VARCHAR(50), nullable=False)
    email: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    first_name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(VARCHAR(50), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    household_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("households.id"), nullable=True
    )
    permission_level_group: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, default="NUS"
    )
    permission_level_code: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
