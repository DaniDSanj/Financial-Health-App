"""Test: scripts/purge_login_audit_log.py borra solo filas >90 días.

FR-012, CHK004/CHK005.
"""

import importlib.util
import pathlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "purge_login_audit_log_script", _SCRIPTS_DIR / "purge_login_audit_log.py"
)
assert _spec is not None and _spec.loader is not None
_purge_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_purge_module)
purge_login_audit_log = _purge_module.purge_login_audit_log


def _insert_audit_row(db: Session, *, occurred_at: datetime) -> int:
    row_id = db.execute(
        text(
            "INSERT INTO login_audit_log (attempted_identifier, result, occurred_at) "
            "VALUES ('test-user', 'failure', :occurred_at) RETURNING id"
        ),
        {"occurred_at": occurred_at},
    ).scalar_one()
    return row_id


def test_purge_deletes_rows_older_than_90_days(db_session: Session) -> None:
    now = datetime.now(UTC)
    old_id = _insert_audit_row(db_session, occurred_at=now - timedelta(days=91))
    db_session.commit()

    deleted = purge_login_audit_log(db_session, now=now)
    db_session.commit()

    assert deleted == 1
    remaining = db_session.execute(
        text("SELECT id FROM login_audit_log WHERE id = :id"), {"id": old_id}
    ).first()
    assert remaining is None


def test_purge_retains_rows_within_90_days(db_session: Session) -> None:
    now = datetime.now(UTC)
    recent_id = _insert_audit_row(db_session, occurred_at=now - timedelta(days=89))
    db_session.commit()

    purge_login_audit_log(db_session, now=now)
    db_session.commit()

    remaining = db_session.execute(
        text("SELECT id FROM login_audit_log WHERE id = :id"), {"id": recent_id}
    ).first()
    assert remaining is not None


def test_purge_boundary_exactly_90_days_is_retained(db_session: Session) -> None:
    """El límite exacto (occurred_at = now - 90 días) NO se borra: el corte es
    estrictamente "más de 90 días" (occurred_at < cutoff), no "90 días o más"."""
    now = datetime.now(UTC)
    boundary_id = _insert_audit_row(db_session, occurred_at=now - timedelta(days=90))
    db_session.commit()

    purge_login_audit_log(db_session, now=now)
    db_session.commit()

    remaining = db_session.execute(
        text("SELECT id FROM login_audit_log WHERE id = :id"), {"id": boundary_id}
    ).first()
    assert remaining is not None
