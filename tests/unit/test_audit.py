"""Test unitario de record_login_attempt (FR-012): escribe la fila de
auditoría correcta."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from financial_health_app.auth.audit import LoginResult, record_login_attempt
from financial_health_app.models.login_audit_log import LoginAuditLog
from financial_health_app.models.user import User


@pytest.fixture
def seeded_user(db_session: Session) -> User:
    user = User(
        username="jdoe",
        email="jdoe@example.com",
        password_hash="dummy-hash",
        first_name="Jane",
        permission_level_code="MEM",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.parametrize("result", ["success", "failure", "locked"])
def test_record_login_attempt_writes_correct_result(
    db_session: Session, seeded_user: User, result: LoginResult
) -> None:
    record_login_attempt(
        db_session, user_id=seeded_user.id, identifier="jdoe", result=result
    )
    db_session.commit()

    row = db_session.scalars(
        select(LoginAuditLog).where(LoginAuditLog.user_id == seeded_user.id)
    ).one()
    assert row.result == result
    assert row.attempted_identifier == "jdoe"
    assert row.occurred_at is not None


def test_record_login_attempt_allows_null_user_id_for_unknown_identifier(
    db_session: Session,
) -> None:
    record_login_attempt(
        db_session, user_id=None, identifier="noexiste", result="failure"
    )
    db_session.commit()

    row = db_session.scalars(
        select(LoginAuditLog).where(LoginAuditLog.attempted_identifier == "noexiste")
    ).one()
    assert row.user_id is None
    assert row.result == "failure"
