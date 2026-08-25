"""Verifica que la migración inicial crea el esquema esperado y siembra el grupo NUS."""

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


def test_migration_creates_all_tables(db_session: Session) -> None:
    assert db_session.bind is not None
    inspector = inspect(db_session.bind)
    tables = set(inspector.get_table_names())
    assert {
        "keys_catalog",
        "households",
        "users",
        "user_sessions",
        "login_audit_log",
    } <= tables


def test_migration_seeds_nus_group(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            "SELECT code, is_header, sort_order FROM keys_catalog "
            "WHERE group_code = 'NUS' ORDER BY sort_order"
        )
    ).all()
    assert [(r.code, r.is_header, r.sort_order) for r in rows] == [
        (None, True, 0),
        ("ADM", False, 1),
        ("MEM", False, 2),
        ("VIS", False, 3),
    ]
