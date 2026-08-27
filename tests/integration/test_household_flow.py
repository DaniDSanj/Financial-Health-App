"""Tests de integración del flujo de gestión de hogares (US2/US3)."""

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from financial_health_app.auth.hashing import hash_password
from financial_health_app.models.household import Household
from financial_health_app.models.household_invitation import HouseholdInvitation
from financial_health_app.models.household_invitation_attempt_log import (
    HouseholdInvitationAttemptLog,
)
from financial_health_app.models.user import User

_CODE_RE = re.compile(r"<strong>([^<]+)</strong>")


def _make_user(db_session: Session, *, username: str, email: str) -> User:
    user = User(
        username=username,
        email=email,
        password_hash=hash_password("Segura123!"),
        first_name="Jane",
        permission_level_code="MEM",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login(client, *, username: str) -> None:
    client.post("/login", data={"identifier": username, "password": "Segura123!"})


# --- US2: crear un hogar nuevo ------------------------------------------------


def test_create_household_associates_user_as_admin(client, db_session: Session) -> None:
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")

    response = client.post(
        "/household/create", data={"name": "Mi Hogar"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/household"

    user = db_session.scalars(select(User).where(User.username == "jdoe")).one()
    assert user.household_id is not None
    assert user.permission_level_code == "ADM"


def test_create_household_persists_created_by(client, db_session: Session) -> None:
    user = _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")

    client.post("/household/create", data={"name": "Mi Hogar"})

    household = db_session.scalars(select(Household)).one()
    assert household.created_by == user.id


def test_create_household_rejected_if_already_has_household(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")

    client.post("/household/create", data={"name": "Primer Hogar"})
    response = client.post(
        "/household/create", data={"name": "Segundo Hogar"}, follow_redirects=False
    )
    assert response.status_code == 409

    households = db_session.scalars(select(Household)).all()
    assert len(households) == 1


def test_create_household_empty_name_rejected(client, db_session: Session) -> None:
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")

    response = client.post("/household/create", data={"name": ""})
    assert response.status_code == 422
    assert db_session.scalars(select(Household)).first() is None


def test_create_household_whitespace_only_name_rejected(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")

    response = client.post("/household/create", data={"name": "   "})
    assert response.status_code == 422


def test_create_household_name_over_100_chars_rejected(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")

    response = client.post("/household/create", data={"name": "n" * 101})
    assert response.status_code == 422


def test_create_household_duplicate_names_both_succeed(
    client, db_session: Session
) -> None:
    """FR-014: el nombre del hogar no es único — dos hogares con el mismo nombre
    son ambos válidos."""
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _make_user(db_session, username="asmith", email="asmith@example.com")

    _login(client, username="jdoe")
    response_1 = client.post(
        "/household/create", data={"name": "Casa Familiar"}, follow_redirects=False
    )
    assert response_1.status_code == 303

    client.post("/logout")
    _login(client, username="asmith")
    response_2 = client.post(
        "/household/create", data={"name": "Casa Familiar"}, follow_redirects=False
    )
    assert response_2.status_code == 303

    households = db_session.scalars(select(Household)).all()
    assert len(households) == 2
    assert all(h.name == "Casa Familiar" for h in households)


def test_household_page_without_household_shows_create_and_join_forms(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")

    response = client.get("/household")
    assert response.status_code == 200
    assert 'action="/household/create"' in response.text
    assert 'action="/household/join"' in response.text


def test_household_page_with_household_shows_status_and_invite_form(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")
    client.post("/household/create", data={"name": "Mi Hogar"})

    response = client.get("/household")
    assert response.status_code == 200
    assert "Mi Hogar" in response.text
    assert 'action="/household/invite"' in response.text


def test_welcome_page_links_to_household_when_no_household(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")

    response = client.get("/")
    assert response.status_code == 200
    assert "/household" in response.text


def test_welcome_page_shows_household_name_when_associated(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")
    client.post("/household/create", data={"name": "Mi Hogar"})

    response = client.get("/")
    assert response.status_code == 200
    assert "Mi Hogar" in response.text


# --- US3: asociación mediante código de invitación ----------------------------


def _generate_invite_code(client) -> str:
    """Genera un código desde un miembro ya logueado con hogar, devuelve el
    código en claro extraído del HTML (solo se muestra una vez, FR-007)."""
    response = client.post("/household/invite")
    assert response.status_code == 200
    match = _CODE_RE.search(response.text)
    assert match is not None, "El código no se encontró en la respuesta"
    return match.group(1)


def test_join_with_valid_code_associates_as_member_and_invalidates_code(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="owner", email="owner@example.com")
    _login(client, username="owner")
    client.post("/household/create", data={"name": "Hogar de Owner"})
    code = _generate_invite_code(client)
    client.post("/logout")

    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")
    response = client.post(
        "/household/join", data={"code": code}, follow_redirects=False
    )
    assert response.status_code == 303

    jdoe = db_session.scalars(select(User).where(User.username == "jdoe")).one()
    assert jdoe.household_id is not None
    assert jdoe.permission_level_code == "MEM"

    invitation = db_session.scalars(select(HouseholdInvitation)).one()
    assert invitation.used_at is not None
    assert invitation.used_by == jdoe.id


def test_join_with_already_used_code_rejected(client, db_session: Session) -> None:
    _make_user(db_session, username="owner", email="owner@example.com")
    _login(client, username="owner")
    client.post("/household/create", data={"name": "Hogar de Owner"})
    code = _generate_invite_code(client)
    client.post("/logout")

    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")
    client.post("/household/join", data={"code": code})
    client.post("/logout")

    _make_user(db_session, username="asmith", email="asmith@example.com")
    _login(client, username="asmith")
    response = client.post(
        "/household/join", data={"code": code}, follow_redirects=False
    )
    assert response.status_code == 401

    asmith = db_session.scalars(select(User).where(User.username == "asmith")).one()
    assert asmith.household_id is None


def test_join_with_expired_code_rejected(client, db_session: Session) -> None:
    owner = _make_user(db_session, username="owner", email="owner@example.com")
    household = Household(name="Hogar de Owner", created_by=owner.id)
    db_session.add(household)
    db_session.commit()
    db_session.refresh(household)

    from financial_health_app.auth.invite_code import hash_code

    expired = HouseholdInvitation(
        household_id=household.id,
        code_hash=hash_code("EXPIRED1"),
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        created_by=owner.id,
    )
    db_session.add(expired)
    db_session.commit()

    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")
    response = client.post(
        "/household/join", data={"code": "EXPIRED1"}, follow_redirects=False
    )
    assert response.status_code == 401


def test_join_with_nonexistent_code_rejected(client, db_session: Session) -> None:
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")
    response = client.post(
        "/household/join", data={"code": "NOPENOPE"}, follow_redirects=False
    )
    assert response.status_code == 401


def test_join_rejected_if_user_already_has_household(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="owner", email="owner@example.com")
    _login(client, username="owner")
    client.post("/household/create", data={"name": "Hogar de Owner"})
    code = _generate_invite_code(client)
    client.post("/logout")

    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")
    client.post("/household/create", data={"name": "Otro Hogar"})

    response = client.post(
        "/household/join", data={"code": code}, follow_redirects=False
    )
    assert response.status_code == 409


def test_invite_code_shown_only_once_not_recoverable(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="owner", email="owner@example.com")
    _login(client, username="owner")
    client.post("/household/create", data={"name": "Hogar de Owner"})
    _generate_invite_code(client)

    page = client.get("/household")
    assert page.status_code == 200
    assert "invite_code" not in page.text
    assert _CODE_RE.search(page.text) is None


def test_sixth_join_attempt_is_rejected_even_with_correct_code(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="owner", email="owner@example.com")
    _login(client, username="owner")
    client.post("/household/create", data={"name": "Hogar de Owner"})
    code = _generate_invite_code(client)
    client.post("/logout")

    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")
    for _ in range(5):
        client.post("/household/join", data={"code": "WRONGCOD"})

    response = client.post(
        "/household/join", data={"code": code}, follow_redirects=False
    )
    assert response.status_code == 401
    jdoe = db_session.scalars(select(User).where(User.username == "jdoe")).one()
    assert jdoe.household_id is None


def test_join_writes_audit_rows_with_correct_results(
    client, db_session: Session
) -> None:
    _make_user(db_session, username="owner", email="owner@example.com")
    _login(client, username="owner")
    client.post("/household/create", data={"name": "Hogar de Owner"})
    code = _generate_invite_code(client)
    client.post("/logout")

    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")
    client.post("/household/join", data={"code": "WRONGCOD"})
    client.post("/household/join", data={"code": code})

    jdoe = db_session.scalars(select(User).where(User.username == "jdoe")).one()
    rows = db_session.scalars(
        select(HouseholdInvitationAttemptLog)
        .where(HouseholdInvitationAttemptLog.user_id == jdoe.id)
        .order_by(HouseholdInvitationAttemptLog.id)
    ).all()
    assert [r.result for r in rows] == ["failure", "success"]
    assert rows[0].household_id is None
    assert rows[1].household_id is not None


def test_join_failure_audit_identifies_household_for_used_code(
    client, db_session: Session
) -> None:
    """FR-015: si el código introducido corresponde a una invitación real ya
    usada, el log de auditoría SÍ identifica household_id (distinto de un código
    que no corresponde a ninguna invitación en absoluto)."""
    _make_user(db_session, username="owner", email="owner@example.com")
    _login(client, username="owner")
    client.post("/household/create", data={"name": "Hogar de Owner"})
    code = _generate_invite_code(client)
    client.post("/logout")

    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")
    client.post("/household/join", data={"code": code})
    client.post("/logout")

    _make_user(db_session, username="asmith", email="asmith@example.com")
    _login(client, username="asmith")
    client.post("/household/join", data={"code": code})

    asmith = db_session.scalars(select(User).where(User.username == "asmith")).one()
    row = db_session.scalars(
        select(HouseholdInvitationAttemptLog).where(
            HouseholdInvitationAttemptLog.user_id == asmith.id
        )
    ).one()
    assert row.result == "failure"
    assert row.household_id is not None


def test_sixth_attempt_writes_locked_audit_row(client, db_session: Session) -> None:
    _make_user(db_session, username="jdoe", email="jdoe@example.com")
    _login(client, username="jdoe")
    for _ in range(5):
        client.post("/household/join", data={"code": "WRONGCOD"})
    client.post("/household/join", data={"code": "WRONGCOD"})

    jdoe = db_session.scalars(select(User).where(User.username == "jdoe")).one()
    rows = db_session.scalars(
        select(HouseholdInvitationAttemptLog)
        .where(HouseholdInvitationAttemptLog.user_id == jdoe.id)
        .order_by(HouseholdInvitationAttemptLog.id)
    ).all()
    assert [r.result for r in rows] == ["failure"] * 5 + ["locked"]
