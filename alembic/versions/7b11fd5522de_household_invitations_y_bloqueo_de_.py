"""household invitations y bloqueo de codigo

Revision ID: 7b11fd5522de
Revises: 13b5ce2f3fb6
Create Date: 2026-08-26 14:39:33.512243

Orden de creación (ver specs/002-user-registration-households/data-model.md →
"Orden de creación"): sin dependencia circular como en 001 — households y users
ya existen desde la migración inicial, así que household_invitations y
household_invitation_attempts_log pueden declarar sus FKs hacia ambas desde su
propia creación:

1. household_invitations (depende de households y users, ya existentes).
2. household_invitation_attempts_log (depende de users y households, ya
   existentes).
3. ALTER TABLE users ADD COLUMN failed_invite_attempts / invite_locked_until —
   aditivo, con DEFAULT seguro; requiere UAT humana antes de aplicarse fuera de
   un entorno de test (tabla con datos reales, ver tasks.md T022).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b11fd5522de"
down_revision: str | Sequence[str] | None = "13b5ce2f3fb6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. household_invitations.
    op.create_table(
        "household_invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.VARCHAR(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(used_at IS NULL) = (used_by IS NULL)",
            name="ck_household_invitations_used_consistency",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["used_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_household_invitations_household_id",
        "household_invitations",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_household_invitations_created_by",
        "household_invitations",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        "ix_household_invitations_used_by",
        "household_invitations",
        ["used_by"],
        unique=False,
    )
    op.create_index(
        "ix_household_invitations_code_hash",
        "household_invitations",
        ["code_hash"],
        unique=False,
    )

    # 2. household_invitation_attempts_log.
    op.create_table(
        "household_invitation_attempts_log",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=True),
        sa.Column("result", sa.VARCHAR(length=20), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "result IN ('success', 'failure', 'locked')",
            name="ck_household_invitation_attempts_log_result",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_household_invitation_attempts_log_user_id",
        "household_invitation_attempts_log",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_household_invitation_attempts_log_household_id",
        "household_invitation_attempts_log",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_household_invitation_attempts_log_occurred_at",
        "household_invitation_attempts_log",
        ["occurred_at"],
        unique=False,
        postgresql_using="brin",
    )

    # 3. ALTER TABLE users — aditivo (ver nota de UAT en el docstring del módulo).
    op.add_column(
        "users",
        sa.Column(
            "failed_invite_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "users",
        sa.Column("invite_locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "invite_locked_until")
    op.drop_column("users", "failed_invite_attempts")

    op.drop_index(
        "ix_household_invitation_attempts_log_occurred_at",
        table_name="household_invitation_attempts_log",
        postgresql_using="brin",
    )
    op.drop_index(
        "ix_household_invitation_attempts_log_household_id",
        table_name="household_invitation_attempts_log",
    )
    op.drop_index(
        "ix_household_invitation_attempts_log_user_id",
        table_name="household_invitation_attempts_log",
    )
    op.drop_table("household_invitation_attempts_log")

    op.drop_index(
        "ix_household_invitations_code_hash", table_name="household_invitations"
    )
    op.drop_index(
        "ix_household_invitations_used_by", table_name="household_invitations"
    )
    op.drop_index(
        "ix_household_invitations_created_by", table_name="household_invitations"
    )
    op.drop_index(
        "ix_household_invitations_household_id", table_name="household_invitations"
    )
    op.drop_table("household_invitations")
