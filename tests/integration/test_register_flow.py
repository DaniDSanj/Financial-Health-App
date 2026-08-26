"""Tests de integración del flujo de registro (US1)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from financial_health_app.models.user import User

_VALID_DATA = {
    "first_name": "Jane",
    "last_name": "Doe",
    "username": "jdoe",
    "email": "jdoe@example.com",
    "password": "Segura123!",
}


def _post_register(client, **overrides):
    data = {**_VALID_DATA, **overrides}
    return client.post("/register", data=data, follow_redirects=False)


# --- Acceptance Scenario 1: alta con datos válidos ---------------------------


def test_register_success_creates_account_and_auto_logs_in(client) -> None:
    response = _post_register(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session" in response.cookies


def test_register_success_persists_user_with_created_at(
    client, db_session: Session
) -> None:
    _post_register(client)
    user = db_session.scalars(select(User).where(User.username == "jdoe")).one()
    assert user.created_at is not None
    assert user.household_id is None
    assert user.permission_level_code == "MEM"


def test_register_last_name_is_optional(client, db_session: Session) -> None:
    data = {**_VALID_DATA}
    del data["last_name"]
    response = client.post("/register", data=data, follow_redirects=False)
    assert response.status_code == 303
    user = db_session.scalars(select(User).where(User.username == "jdoe")).one()
    assert user.last_name is None


# --- Acceptance Scenario 2: username/email duplicado (FR-002) ----------------


def test_duplicate_username_different_capitalization_is_rejected(client) -> None:
    _post_register(client)
    response = _post_register(client, username="JDoe", email="other@example.com")
    assert response.status_code == 409


def test_duplicate_email_different_capitalization_is_rejected(client) -> None:
    _post_register(client)
    response = _post_register(client, username="other", email="JDOE@EXAMPLE.COM")
    assert response.status_code == 409


def test_duplicate_registration_does_not_create_second_row(
    client, db_session: Session
) -> None:
    _post_register(client)
    _post_register(client, email="other@example.com")

    count = len(db_session.scalars(select(User).where(User.username == "jdoe")).all())
    assert count == 1


# --- Acceptance Scenario 3: contraseña fuera de rango (FR-011) ---------------


def test_password_too_short_is_rejected_before_persisting(
    client, db_session: Session
) -> None:
    response = _post_register(client, password="short1")
    assert response.status_code == 422
    assert "entre 8 y 128 caracteres" in response.text
    assert db_session.scalars(select(User)).first() is None


def test_password_too_long_is_rejected(client) -> None:
    response = _post_register(client, password="a" * 129)
    assert response.status_code == 422
    assert "entre 8 y 128 caracteres" in response.text


def test_password_exactly_8_chars_is_accepted(client) -> None:
    response = _post_register(client, password="Abcdefg1")
    assert response.status_code == 303


def test_password_exactly_128_chars_is_accepted(client) -> None:
    response = _post_register(client, password="Ab1" + "x" * 125)
    assert response.status_code == 303


# --- FR-011: límites de longitud y charset ASCII ------------------------------


def test_username_over_max_length_is_rejected(client) -> None:
    response = _post_register(client, username="u" * 51)
    assert response.status_code == 422
    assert "usuario no puede superar los 50 caracteres" in response.text


def test_email_over_max_length_is_rejected(client) -> None:
    long_local = "a" * 250
    response = _post_register(client, email=f"{long_local}@example.com")
    assert response.status_code == 422
    assert "email no puede superar los 255 caracteres" in response.text


def test_first_name_over_max_length_is_rejected(client) -> None:
    response = _post_register(client, first_name="n" * 101)
    assert response.status_code == 422
    assert "nombre no puede superar los 100 caracteres" in response.text


def test_last_name_over_max_length_is_rejected(client) -> None:
    response = _post_register(client, last_name="n" * 51)
    assert response.status_code == 422
    assert "apellidos no pueden superar los 50 caracteres" in response.text


def test_username_with_non_ascii_characters_is_rejected(client) -> None:
    response = _post_register(client, username="joséño")
    assert response.status_code == 422
    assert "usuario solo puede contener caracteres ASCII" in response.text


def test_email_with_non_ascii_characters_is_rejected(client) -> None:
    response = _post_register(client, email="josé@example.com")
    assert response.status_code == 422
    assert "email solo puede contener caracteres ASCII" in response.text


def test_invalid_email_syntax_is_rejected(client) -> None:
    response = _post_register(client, email="not-an-email")
    assert response.status_code == 422
    assert "email no tiene un formato válido" in response.text


def test_different_validation_failures_produce_different_messages(client) -> None:
    """UAT 2026-08-26: antes de este cambio, todos los rechazos de FR-011
    devolvían el mismo mensaje genérico, sin indicar qué corregir."""
    password_response = _post_register(client, password="short1")
    username_response = _post_register(client, username="u" * 51)
    assert password_response.text != username_response.text


# --- FR-009: login inmediato sin paso adicional -------------------------------


def test_welcome_page_reachable_immediately_after_register(client) -> None:
    _post_register(client)
    response = client.get("/")
    assert response.status_code == 200
    assert "Jane" in response.text
