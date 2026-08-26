"""Verifica que la migración de 002 crea household_invitations,
household_invitation_attempts_log, y extiende users con las 2 columnas nuevas."""

from sqlalchemy import inspect
from sqlalchemy.orm import Session


def test_migration_creates_invitation_tables(db_session: Session) -> None:
    assert db_session.bind is not None
    inspector = inspect(db_session.bind)
    tables = set(inspector.get_table_names())
    assert {"household_invitations", "household_invitation_attempts_log"} <= tables


def test_migration_extends_users_with_invite_lockout_columns(
    db_session: Session,
) -> None:
    assert db_session.bind is not None
    inspector = inspect(db_session.bind)
    columns = {c["name"] for c in inspector.get_columns("users")}
    assert {"failed_invite_attempts", "invite_locked_until"} <= columns
