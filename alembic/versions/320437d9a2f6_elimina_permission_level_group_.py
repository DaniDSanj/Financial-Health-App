"""elimina permission level group redundante

Revision ID: 320437d9a2f6
Revises: 7b11fd5522de
Create Date: 2026-08-27 00:22:34.345110

Ver docs/ADR/records/ADR-0008-eliminacion-columna-permission-level-group.md.
`users.permission_level_group` nunca tomó otro valor que `'NUS'` desde su
creación en la migración inicial (001-login-skeleton) — se elimina como
columna de fila junto con la FK compuesta que la usaba, y la asociación al
grupo `NUS` pasa a documentarse vía `COMMENT ON COLUMN` + metadato del modelo
SQLAlchemy, no vía dato de fila. Tabla con datos ya existentes: requiere UAT
humana explícita antes de aplicarse fuera de un entorno de test.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "320437d9a2f6"
down_revision: str | Sequence[str] | None = "7b11fd5522de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMN_COMMENT = (
    "Nivel de permisos del usuario. Referencia keys_catalog.code "
    "WHERE group_code = NUS (ver ADR-0008) - sin FK de BD, validado en "
    "la capa de aplicacion."
)


def upgrade() -> None:
    op.drop_constraint("fk_users_permission_level", "users", type_="foreignkey")
    op.drop_column("users", "permission_level_group")
    # COMMENT ON no admite bind params via el driver (ver psycopg SyntaxError con
    # $1) — seguro interpolar aqui: _COLUMN_COMMENT es una constante del modulo
    # sin comillas simples, no entrada de usuario.
    op.execute(f"COMMENT ON COLUMN users.permission_level_code IS '{_COLUMN_COMMENT}'")


def downgrade() -> None:
    op.execute("COMMENT ON COLUMN users.permission_level_code IS NULL")
    op.add_column(
        "users",
        sa.Column(
            "permission_level_group",
            sa.CHAR(length=3),
            nullable=False,
            server_default="NUS",
        ),
    )
    op.alter_column("users", "permission_level_group", server_default=None)
    op.create_foreign_key(
        "fk_users_permission_level",
        "users",
        "keys_catalog",
        ["permission_level_group", "permission_level_code"],
        ["group_code", "code"],
    )
