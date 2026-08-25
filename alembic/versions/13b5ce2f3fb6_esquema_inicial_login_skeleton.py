"""esquema inicial login skeleton

Revision ID: 13b5ce2f3fb6
Revises:
Create Date: 2026-08-25 15:30:50.159604

Orden de creación (ver specs/001-login-skeleton/data-model.md → "Orden de creación"),
necesario por la dependencia circular de FKs de auditoría entre
keys_catalog/households/users:

1. keys_catalog y households, con created_by/updated_by nullable pero SIN la FK
   todavía.
2. users (ya puede declarar sus FKs hacia households y keys_catalog, que ya existen).
3. user_sessions y login_audit_log (dependen solo de users).
4. ALTER TABLE para añadir las FK de auditoría de keys_catalog/households hacia
   users, ahora que users ya existe.
5. Seed del grupo NUS en keys_catalog (created_by/updated_by en NULL — no hay
   usuario válido todavía al que atribuir la primera fila del sistema).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "13b5ce2f3fb6"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. keys_catalog y households, sin FK de auditoría todavía.
    op.create_table(
        "keys_catalog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_code", sa.CHAR(length=3), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_header", sa.Boolean(), nullable=False),
        sa.Column("code", sa.CHAR(length=3), nullable=True),
        sa.Column("description", sa.VARCHAR(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "group_code", "code", name="uq_keys_catalog_group_code_code"
        ),
    )
    op.create_index(
        "ix_keys_catalog_group_code", "keys_catalog", ["group_code"], unique=False
    )

    op.create_table(
        "households",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.VARCHAR(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. users — ya puede declarar sus FKs hacia households y keys_catalog.
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.VARCHAR(length=50), nullable=False),
        sa.Column("email", sa.VARCHAR(length=255), nullable=False),
        sa.Column("password_hash", sa.VARCHAR(length=255), nullable=False),
        sa.Column("first_name", sa.VARCHAR(length=100), nullable=False),
        sa.Column("last_name", sa.VARCHAR(length=50), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("household_id", sa.Integer(), nullable=True),
        sa.Column("permission_level_group", sa.CHAR(length=3), nullable=False),
        sa.Column("permission_level_code", sa.CHAR(length=3), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(
            ["permission_level_group", "permission_level_code"],
            ["keys_catalog.group_code", "keys_catalog.code"],
            name="fk_users_permission_level",
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_users_email_lower",
        "users",
        [sa.literal_column("lower(email)")],
        unique=True,
    )
    op.create_index(
        "ix_users_username_lower",
        "users",
        [sa.literal_column("lower(username)")],
        unique=True,
    )

    # 3. user_sessions y login_audit_log — dependen solo de users.
    op.create_table(
        "login_audit_log",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("attempted_identifier", sa.VARCHAR(length=255), nullable=False),
        sa.Column("result", sa.VARCHAR(length=20), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "result IN ('success', 'failure', 'locked')",
            name="ck_login_audit_log_result",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_login_audit_log_occurred_at",
        "login_audit_log",
        ["occurred_at"],
        unique=False,
        postgresql_using="brin",
    )

    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_token", sa.VARCHAR(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("session_token"),
    )

    # 4. Ahora que users existe, añadir las FK de auditoría pendientes de
    #    keys_catalog/households.
    op.create_foreign_key(
        "fk_keys_catalog_created_by_users",
        "keys_catalog",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_keys_catalog_updated_by_users",
        "keys_catalog",
        "users",
        ["updated_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_households_created_by_users",
        "households",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_households_updated_by_users",
        "households",
        "users",
        ["updated_by"],
        ["id"],
    )

    # 5. Seed del grupo NUS (niveles de usuario) en keys_catalog.
    keys_catalog = sa.table(
        "keys_catalog",
        sa.column("group_code", sa.CHAR(3)),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_header", sa.Boolean()),
        sa.column("code", sa.CHAR(3)),
        sa.column("description", sa.VARCHAR(100)),
        sa.column("version", sa.Integer()),
    )
    op.bulk_insert(
        keys_catalog,
        [
            {
                "group_code": "NUS",
                "sort_order": 0,
                "is_header": True,
                "code": None,
                "description": "Niveles de usuario",
                "version": 1,
            },
            {
                "group_code": "NUS",
                "sort_order": 1,
                "is_header": False,
                "code": "ADM",
                "description": "Administrador (todos los permisos)",
                "version": 1,
            },
            {
                "group_code": "NUS",
                "sort_order": 2,
                "is_header": False,
                "code": "MEM",
                "description": "Miembro (ver y editar, no borrar)",
                "version": 1,
            },
            {
                "group_code": "NUS",
                "sort_order": 3,
                "is_header": False,
                "code": "VIS",
                "description": "Visor (solo lectura)",
                "version": 1,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("user_sessions")
    op.drop_index(
        "ix_login_audit_log_occurred_at",
        table_name="login_audit_log",
        postgresql_using="brin",
    )
    op.drop_table("login_audit_log")
    op.drop_constraint(
        "fk_households_updated_by_users", "households", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_households_created_by_users", "households", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_keys_catalog_updated_by_users", "keys_catalog", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_keys_catalog_created_by_users", "keys_catalog", type_="foreignkey"
    )
    op.drop_index("ix_users_username_lower", table_name="users")
    op.drop_index("ix_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_table("households")
    op.drop_index("ix_keys_catalog_group_code", table_name="keys_catalog")
    op.drop_table("keys_catalog")
