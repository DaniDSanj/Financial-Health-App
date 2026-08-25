"""Tests de integración del flujo de login (US1/US2/US3)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from financial_health_app.auth.hashing import hash_password
from financial_health_app.models.login_audit_log import LoginAuditLog
from financial_health_app.models.user import User


@pytest.fixture
def jdoe(db_session: Session) -> User:
    user = User(
        username="jdoe",
        email="jdoe@example.com",
        password_hash=hash_password("Segura123!"),
        first_name="Jane",
        permission_level_code="MEM",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# --- US1: login con credenciales válidas -------------------------------------


def test_login_success_redirects_to_welcome_with_session_cookie(
    client, jdoe: User
) -> None:
    response = client.post(
        "/login",
        data={"identifier": "jdoe", "password": "Segura123!"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session" in response.cookies


def test_login_success_writes_success_audit_row(
    client, jdoe: User, db_session: Session
) -> None:
    client.post(
        "/login",
        data={"identifier": "jdoe", "password": "Segura123!"},
        follow_redirects=False,
    )
    row = db_session.scalars(
        select(LoginAuditLog).where(LoginAuditLog.user_id == jdoe.id)
    ).one()
    assert row.result == "success"


def test_login_case_insensitive_identifier_resolves_same_user(
    client, jdoe: User
) -> None:
    response = client.post(
        "/login",
        data={"identifier": "JDoe", "password": "Segura123!"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_login_case_insensitive_email_resolves_same_user(client, jdoe: User) -> None:
    response = client.post(
        "/login",
        data={"identifier": "JDOE@EXAMPLE.COM", "password": "Segura123!"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_welcome_page_shows_real_name(client, jdoe: User) -> None:
    client.post("/login", data={"identifier": "jdoe", "password": "Segura123!"})
    response = client.get("/")
    assert response.status_code == 200
    assert "Jane" in response.text


def test_logout_invalidates_session_and_redirects_to_login(client, jdoe: User) -> None:
    client.post("/login", data={"identifier": "jdoe", "password": "Segura123!"})
    logout_response = client.post("/logout", follow_redirects=False)
    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/login"

    welcome_response = client.get("/", follow_redirects=False)
    assert welcome_response.status_code == 303
    assert welcome_response.headers["location"] == "/login"


def test_welcome_without_session_redirects_to_login(client) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


# --- US2: rechazo de credenciales inválidas ----------------------------------


def test_wrong_password_shows_generic_error_and_creates_no_session(
    client, jdoe: User
) -> None:
    response = client.post(
        "/login",
        data={"identifier": "jdoe", "password": "Incorrecta456!"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert "session" not in response.cookies


def test_nonexistent_identifier_shows_same_generic_error(client, jdoe: User) -> None:
    wrong_password = client.post(
        "/login",
        data={"identifier": "jdoe", "password": "Incorrecta456!"},
        follow_redirects=False,
    )
    nonexistent = client.post(
        "/login",
        data={"identifier": "noexiste", "password": "cualquiera"},
        follow_redirects=False,
    )
    assert nonexistent.status_code == wrong_password.status_code == 401
    assert nonexistent.text == wrong_password.text


def test_failed_attempts_write_failure_audit_rows(
    client, jdoe: User, db_session: Session
) -> None:
    client.post("/login", data={"identifier": "jdoe", "password": "Incorrecta456!"})
    client.post("/login", data={"identifier": "noexiste", "password": "x"})

    rows = db_session.scalars(select(LoginAuditLog)).all()
    assert all(r.result == "failure" for r in rows)


def test_nonexistent_identifier_invokes_dummy_hash_verification(
    client, jdoe: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mitigación de timing (ADR-0004): la ruta 'no existe' debe invocar la misma
    verificación Argon2id que la ruta 'password incorrecta', vía mock/spy (sin
    medir reloj real — evita un test inestable en CI)."""
    import financial_health_app.routers.login as login_module

    calls: list[tuple[str, str | None]] = []
    original = login_module.verify_password_timing_safe

    def spy(password: str, hash_or_none: str | None) -> bool:
        calls.append((password, hash_or_none))
        return original(password, hash_or_none)

    # Parchear en el módulo que USA la función (routers.login la importó por
    # nombre), no en el módulo donde se define — de lo contrario el monkeypatch no
    # afecta a la referencia ya vinculada en routers/login.py.
    monkeypatch.setattr(login_module, "verify_password_timing_safe", spy)

    client.post("/login", data={"identifier": "noexiste", "password": "x"})
    client.post("/login", data={"identifier": "jdoe", "password": "Incorrecta456!"})

    assert len(calls) == 2
    assert calls[0][1] is None  # ruta "no existe" -> hash_or_none=None
    assert calls[1][1] is not None  # ruta "password incorrecta" -> hash real


def test_empty_fields_return_422_without_querying_db(client) -> None:
    # Starlette/python-multipart tratan un campo Form con valor vacío como
    # "ausente" (verificado también enviando el body crudo
    # application/x-www-form-urlencoded, mismo resultado) — por eso basta con
    # Form(...) (requerido) en login.py, sin min_length adicional: la validación
    # de Pydantic rechaza la petición con 422 antes de que el handler llegue a
    # consultar la BD.
    response = client.post("/login", data={"identifier": "", "password": ""})
    assert response.status_code == 422


# --- US3: bloqueo tras intentos fallidos repetidos ---------------------------


def test_sixth_attempt_is_rejected_even_with_correct_password(
    client, jdoe: User
) -> None:
    for _ in range(5):
        client.post("/login", data={"identifier": "jdoe", "password": "Incorrecta456!"})

    response = client.post(
        "/login",
        data={"identifier": "jdoe", "password": "Segura123!"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert "session" not in response.cookies


def test_sixth_attempt_writes_locked_audit_row_not_failure(
    client, jdoe: User, db_session: Session
) -> None:
    for _ in range(5):
        client.post("/login", data={"identifier": "jdoe", "password": "Incorrecta456!"})
    client.post("/login", data={"identifier": "jdoe", "password": "Segura123!"})

    rows = db_session.scalars(
        select(LoginAuditLog)
        .where(LoginAuditLog.user_id == jdoe.id)
        .order_by(LoginAuditLog.id)
    ).all()
    assert [r.result for r in rows] == ["failure"] * 5 + ["locked"]


def test_lockout_auto_resets_after_expiry_without_prior_correct_login(
    client, jdoe: User, db_session: Session
) -> None:
    for _ in range(5):
        client.post("/login", data={"identifier": "jdoe", "password": "Incorrecta456!"})

    # Backdatear locked_until para simular que ya expiraron los 15 minutos.
    db_session.refresh(jdoe)
    jdoe.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    response = client.post(
        "/login",
        data={"identifier": "jdoe", "password": "Segura123!"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
