"""Test: scripts/seed_user.py hashea correctamente y el usuario puede
autenticarse (CHK001)."""

import importlib.util
import pathlib

from sqlalchemy.orm import Session

_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "seed_user_script", _SCRIPTS_DIR / "seed_user.py"
)
assert _spec is not None and _spec.loader is not None
seed_user_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_user_script)


def test_seed_user_hashes_password_not_plaintext(db_session: Session) -> None:
    user = seed_user_script.seed_user(
        db_session, "seeded", "seeded@example.com", "Segura123!", "Seeded"
    )
    db_session.commit()

    assert user.password_hash != "Segura123!"
    assert "Segura123!" not in user.password_hash


def test_seed_user_can_then_authenticate_via_real_login_flow(
    client, db_session: Session
) -> None:
    seed_user_script.seed_user(
        db_session, "seeded2", "seeded2@example.com", "Segura123!", "Seeded"
    )
    db_session.commit()

    response = client.post(
        "/login",
        data={"identifier": "seeded2", "password": "Segura123!"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
