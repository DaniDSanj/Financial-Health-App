"""Test unitario de auth/invite_lockout.py: umbral de 5 fallos, bloqueo 15min,
auto-reseteo (FR-013, mismo patrón que auth/lockout.py de 001)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from financial_health_app.auth.invite_lockout import (
    check_invite_lockout,
    register_failed_invite_attempt,
    reset_invite_lockout,
)
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


def test_check_invite_lockout_false_when_no_locked_until(
    db_session: Session, user: User
) -> None:
    assert check_invite_lockout(user) is False


def test_five_failures_activate_lockout(db_session: Session, user: User) -> None:
    for _ in range(5):
        register_failed_invite_attempt(db_session, user)
    db_session.commit()
    db_session.refresh(user)

    assert user.failed_invite_attempts == 5
    assert user.invite_locked_until is not None
    assert user.invite_locked_until > datetime.now(UTC)
    assert check_invite_lockout(user) is True


def test_fewer_than_five_failures_do_not_lock(db_session: Session, user: User) -> None:
    for _ in range(4):
        register_failed_invite_attempt(db_session, user)
    db_session.commit()
    db_session.refresh(user)

    assert user.failed_invite_attempts == 4
    assert user.invite_locked_until is None
    assert check_invite_lockout(user) is False


def test_invite_lockout_auto_resets_after_expiry(
    db_session: Session, user: User
) -> None:
    for _ in range(5):
        register_failed_invite_attempt(db_session, user)
    db_session.commit()
    db_session.refresh(user)

    user.invite_locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    db_session.refresh(user)

    assert check_invite_lockout(user) is False


def test_reset_invite_lockout_clears_counter_and_lock(
    db_session: Session, user: User
) -> None:
    for _ in range(5):
        register_failed_invite_attempt(db_session, user)
    db_session.commit()
    db_session.refresh(user)

    reset_invite_lockout(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.failed_invite_attempts == 0
    assert user.invite_locked_until is None
