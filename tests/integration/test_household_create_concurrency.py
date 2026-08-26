"""Test de concurrencia de creación de hogar (T008): garantía de FR-008 bajo dos
peticiones simultáneas del mismo usuario.

Patrón "bloqueo observado directamente" (igual que test_lockout_concurrency.py de
001): el propio `UPDATE ... WHERE household_id IS NULL` de `create_household()`
adquiere el lock de fila sobre `users.id` — Postgres serializa la segunda
conexión sin necesitar sincronización adicional más allá de forzar el orden de
arranque con threading.Event, igual que el caso "correcto" (con FOR UPDATE) de
test_lockout_concurrency.py.
"""

import threading

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from financial_health_app.models.user import User
from financial_health_app.routers.household import create_household


def _insert_test_user(engine: Engine) -> int:
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        user = User(
            username="concurrency-household-user",
            email="concurrency-household-user@example.com",
            password_hash="dummy-hash",
            first_name="Concurrency",
            permission_level_group="NUS",
            permission_level_code="MEM",
        )
        session.add(user)
        session.commit()
        return user.id
    finally:
        session.close()


def _cleanup(engine: Engine, user_id: int) -> None:
    with engine.begin() as conn:
        # users.household_id -> households.id: anular antes de borrar el hogar,
        # o la FK impide el DELETE.
        conn.execute(
            text("UPDATE users SET household_id = NULL WHERE id = :uid"),
            {"uid": user_id},
        )
        conn.execute(
            text("DELETE FROM households WHERE created_by = :uid"), {"uid": user_id}
        )
        conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})


def test_concurrent_household_creation_only_one_succeeds_no_orphan(
    db_engine: Engine,
) -> None:
    user_id = _insert_test_user(db_engine)
    lock_acquired = threading.Event()
    release_a = threading.Event()
    session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )
    results: dict[str, object] = {}

    def connection_a() -> None:
        session_a = session_factory()
        try:
            household_a = create_household(session_a, user_id=user_id, name="Hogar A")
            results["a"] = household_a
            lock_acquired.set()
            release_a.wait(timeout=5)
            if household_a is not None:
                session_a.commit()
            else:
                session_a.rollback()
        finally:
            session_a.close()

    def connection_b() -> None:
        # create_household() se bloquea aquí dentro (en su propia sentencia
        # UPDATE) hasta que la conexión A confirme o deshaga — no necesita ningún
        # Event adicional para ser correcto, Postgres ya lo serializa.
        session_b = session_factory()
        try:
            household_b = create_household(session_b, user_id=user_id, name="Hogar B")
            results["b"] = household_b
            if household_b is not None:
                session_b.commit()
            else:
                session_b.rollback()
        finally:
            session_b.close()

    thread_a = threading.Thread(target=connection_a)
    thread_b = threading.Thread(target=connection_b)
    try:
        thread_a.start()
        assert lock_acquired.wait(timeout=5), (
            "La conexión A no completó su intento a tiempo"
        )
        thread_b.start()
        release_a.set()

        thread_a.join(timeout=5)
        thread_b.join(timeout=5)

        outcomes = [results.get("a"), results.get("b")]
        successes = [o for o in outcomes if o is not None]
        failures = [o for o in outcomes if o is None]
        assert len(successes) == 1 and len(failures) == 1, (
            f"Se esperaba exactamente un éxito y un rechazo, se obtuvo {outcomes}"
        )

        with db_engine.connect() as conn:
            household_count = conn.execute(
                text("SELECT COUNT(*) FROM households WHERE created_by = :uid"),
                {"uid": user_id},
            ).scalar_one()
            user_household_id = conn.execute(
                text("SELECT household_id FROM users WHERE id = :uid"), {"uid": user_id}
            ).scalar_one()
        assert household_count == 1, (
            "No debe quedar ningún hogar huérfano: solo el ganador de la carrera "
            "confirma su INSERT"
        )
        assert user_household_id is not None
    finally:
        release_a.set()
        if thread_a.is_alive():
            thread_a.join(timeout=5)
        if thread_b.is_alive():
            thread_b.join(timeout=5)
        _cleanup(db_engine, user_id)
