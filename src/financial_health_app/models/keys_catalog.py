"""Catálogo genérico transversal (grupos de valores de dominio, p. ej. niveles de
usuario)."""

from datetime import datetime

from sqlalchemy import (
    CHAR,
    VARCHAR,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from financial_health_app.db import Base


class KeysCatalog(Base):
    __tablename__ = "keys_catalog"
    __table_args__ = (
        UniqueConstraint("group_code", "code", name="uq_keys_catalog_group_code_code"),
        Index("ix_keys_catalog_group_code", "group_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_code: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_header: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    code: Mapped[str | None] = mapped_column(CHAR(3), nullable=True)
    description: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
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
