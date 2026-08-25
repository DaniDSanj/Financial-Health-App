"""Script de seed: crea un usuario de prueba con contraseña hasheada (CHK001).

Uso: uv run python scripts/seed_user.py <username> <email> <password> <first_name>
     [permission_level_code]

Reemplaza el placeholder manual de hash de quickstart.md — nunca insertar la
contraseña en texto plano directamente en SQL.
"""

import sys

from sqlalchemy.orm import Session

from financial_health_app.auth.hashing import hash_password
from financial_health_app.db import SessionLocal
from financial_health_app.models.user import User


def seed_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    first_name: str,
    permission_level_code: str = "MEM",
) -> User:
    """Crea un usuario con la contraseña hasheada. No hace commit — el llamador
    decide."""
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        first_name=first_name,
        permission_level_code=permission_level_code,
    )
    db.add(user)
    return user


def main() -> None:
    if len(sys.argv) < 5:
        print(
            "Uso: uv run python scripts/seed_user.py <username> <email> <password> "
            "<first_name> [permission_level_code]",
            file=sys.stderr,
        )
        raise SystemExit(1)

    username, email, password, first_name = sys.argv[1:5]
    permission_level_code = sys.argv[5] if len(sys.argv) > 5 else "MEM"

    db = SessionLocal()
    try:
        user = seed_user(
            db, username, email, password, first_name, permission_level_code
        )
        db.commit()
        db.refresh(user)
        print(
            f"Usuario creado: id={user.id} username={user.username} email={user.email}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
