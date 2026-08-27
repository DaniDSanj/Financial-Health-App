"""Test: scripts/purge_household_invitation_attempts_log.py borra solo filas
>90 días (FR-015)."""

import importlib.util
import pathlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from financial_health_app.models.user import User

_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "purge_household_invitation_attempts_log_script",
    _SCRIPTS_DIR / "purge_household_invitation_attempts_log.py",
)
assert _spec is not None and _spec.loader is not None
_purge_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_purge_module)
purge_household_invitation_attempts_log = (
    _purge_module.purge_household_invitation_attempts_log
)


def _insert_attempt_row(db: Session, *, occurred_at: datetime) -> int:
    user = User(
        username="purge-test-user",
        email="purge-test-user@example.com",
        password_hash="h",
        first_name="X",
        permission_level_code="MEM",
    )
    db.add(user)
    db.flush()
    user_id = user.id
    return db.execute(
        text(
            "INSERT INTO household_invitation_attempts_log "
            "(user_id, result, occurred_at) VALUES "
            "(:uid, 'failure', :occurred_at) RETURNING id"
        ),
        {"uid": user_id, "occurred_at": occurred_at},
    ).scalar_one()


def test_purge_deletes_rows_older_than_90_days(db_session: Session) -> None:
    now = datetime.now(UTC)
    old_id = _insert_attempt_row(db_session, occurred_at=now - timedelta(days=91))
    db_session.commit()

    deleted = purge_household_invitation_attempts_log(db_session, now=now)
    db_session.commit()

    assert deleted == 1
    remaining = db_session.execute(
        text("SELECT id FROM household_invitation_attempts_log WHERE id = :id"),
        {"id": old_id},
    ).first()
    assert remaining is None


def test_purge_retains_rows_within_90_days(db_session: Session) -> None:
    now = datetime.now(UTC)
    recent_id = _insert_attempt_row(db_session, occurred_at=now - timedelta(days=89))
    db_session.commit()

    purge_household_invitation_attempts_log(db_session, now=now)
    db_session.commit()

    remaining = db_session.execute(
        text("SELECT id FROM household_invitation_attempts_log WHERE id = :id"),
        {"id": recent_id},
    ).first()
    assert remaining is not None


def test_purge_boundary_exactly_90_days_is_retained(db_session: Session) -> None:
    now = datetime.now(UTC)
    boundary_id = _insert_attempt_row(db_session, occurred_at=now - timedelta(days=90))
    db_session.commit()

    purge_household_invitation_attempts_log(db_session, now=now)
    db_session.commit()

    remaining = db_session.execute(
        text("SELECT id FROM household_invitation_attempts_log WHERE id = :id"),
        {"id": boundary_id},
    ).first()
    assert remaining is not None
