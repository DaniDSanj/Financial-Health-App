"""Test de concurrencia de registro (T003): ventana de carrera SELECT-then-INSERT.

Patrón "bloqueo observado directamente" (igual que test_lockout_concurrency.py de
001): dos conexiones genuinamente independientes (fixture db_engine). No hace
falta un threading.Event explícito alrededor de la comprobación de unicidad — el
propio índice único (ix_users_username_lower) hace que el INSERT/flush de la
conexión B se bloquee en Postgres hasta que la conexión A confirme o deshaga,
igual que el UPDATE condicional de T008 se bloquea por el lock de fila. Solo se
usan los eventos para forzar el orden de arranque (A primero) de forma
determinista, igual que test_lockout_concurrency.py.
"""

import threading

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from financial_health_app.routers.register import register_user


def _delete_test_users(engine: Engine, username: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE username = :u"), {"u": username})


def test_concurrent_registration_same_username_only_one_succeeds(
    db_engine: Engine,
) -> None:
    username = "concurrency-register-user"
    email = "concurrency-register-user@example.com"
    lock_acquired = threading.Event()
    release_a = threading.Event()
    session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )
    results: dict[str, object] = {}

    def connection_a() -> None:
        session_a = session_factory()
        try:
            user_a = register_user(
                session_a,
                username=username,
                email=email,
                password_hash="dummy-hash",
                first_name="A",
                last_name=None,
            )
            results["a"] = user_a
            lock_acquired.set()
            release_a.wait(timeout=5)
            session_a.commit() if user_a is not None else session_a.rollback()
        finally:
            session_a.close()

    def connection_b() -> None:
        # Este flush se bloquea en Postgres hasta que A confirme/deshaga (mismo
        # username en un índice único), no necesita esperar a lock_acquired para
        # ser correcto, pero lo hace igualmente para mantener el orden de arranque
        # determinista del test.
        assert lock_acquired.wait(timeout=5)
        session_b = session_factory()
        try:
            user_b = register_user(
                session_b,
                username=username,
                email=email,
                password_hash="dummy-hash",
                first_name="B",
                last_name=None,
            )
            results["b"] = user_b
            session_b.commit() if user_b is not None else session_b.rollback()
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
            f"Se esperaba exactamente un éxito y un rechazo (409-equivalente), "
            f"se obtuvo {outcomes}"
        )

        with db_engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM users WHERE username = :u"), {"u": username}
            ).scalar_one()
        assert count == 1, (
            "No debe quedar más de una fila insertada para el mismo username"
        )
    finally:
        release_a.set()
        if thread_a.is_alive():
            thread_a.join(timeout=5)
        if thread_b.is_alive():
            thread_b.join(timeout=5)
        _delete_test_users(db_engine, username)
