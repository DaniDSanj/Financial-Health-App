"""Test unitario de lockout.py: umbral de 5 fallos, bloqueo 15min, auto-reseteo.

FR-007, SC-003.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from financial_health_app.auth.lockout import check_lockout, register_failed_attempt
from financial_health_app.models.user import User


@pytest.fixture
def user(db_session: Session) -> User:
    u = User(
        username="jdoe",
        email="jdoe@example.com",
        password_hash="dummy-hash",
        first_name="Jane",
        permission_level_code="MEM",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def test_check_lockout_false_when_no_locked_until(
    db_session: Session, user: User
) -> None:
    assert check_lockout(user) is False


def test_five_failures_activate_lockout(db_session: Session, user: User) -> None:
    for _ in range(5):
        register_failed_attempt(db_session, user)
    db_session.commit()
    db_session.refresh(user)

    assert user.failed_login_attempts == 5
    assert user.locked_until is not None
    assert user.locked_until > datetime.now(UTC)
    assert check_lockout(user) is True


def test_fewer_than_five_failures_do_not_lock(db_session: Session, user: User) -> None:
    for _ in range(4):
        register_failed_attempt(db_session, user)
    db_session.commit()
    db_session.refresh(user)

    assert user.failed_login_attempts == 4
    assert user.locked_until is None
    assert check_lockout(user) is False


def test_lockout_auto_resets_after_expiry(db_session: Session, user: User) -> None:
    for _ in range(5):
        register_failed_attempt(db_session, user)
    db_session.commit()
    db_session.refresh(user)

    user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    db_session.refresh(user)

    assert check_lockout(user) is False
