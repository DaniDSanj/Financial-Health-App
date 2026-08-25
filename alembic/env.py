import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Solo se usa DATABASE_URL de .env como fallback: si el llamador (p. ej. la fixture
# de tests/conftest.py) ya hizo config.set_main_option("sqlalchemy.url", ...) antes
# de invocar Alembic programáticamente, ese valor prevalece — no lo pisamos aquí.
if not config.get_main_option("sqlalchemy.url"):
    # configparser interpreta "%" como carácter de interpolación: escapar como "%%"
    # antes de pasarlo a set_main_option (la URL puede llevar contraseñas URL-encoded
    # con "%").
    _url = os.environ.get("DATABASE_URL", "").replace("%", "%%")
    config.set_main_option("sqlalchemy.url", _url)

# Registra las tablas en Base.metadata; import diferido, tras resolver sqlalchemy.url.
import financial_health_app.models as models  # noqa: E402,F401
from financial_health_app.db import Base  # noqa: E402

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
