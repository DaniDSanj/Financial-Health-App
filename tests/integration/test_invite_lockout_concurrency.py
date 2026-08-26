"""Test de concurrencia determinista del bloqueo de códigos de invitación (T018).

Mismo patrón "bloqueo observado directamente" que test_lockout_concurrency.py de
001 (ver ese fichero para la explicación completa del porqué): dos hilos
genuinamente concurrentes usando `register_failed_invite_attempt` (con
`SELECT ... FOR UPDATE`) no pierden ningún incremento; el control negativo sin
`FOR UPDATE`, con interlineado manual sin hilos, sí lo pierde.
"""

import threading

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from financial_health_app.auth.invite_lockout import register_failed_invite_attempt
from financial_health_app.models.user import User


def _insert_test_user(engine: Engine) -> int:
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        user = User(
            username="concurrency-invite-lockout-user",
            email="concurrency-invite-lockout-user@example.com",
            password_hash="dummy-hash",
            first_name="Concurrency",
            permission_level_code="MEM",
        )
        session.add(user)
        session.commit()
        return user.id
    finally:
        session.close()


def _delete_test_user(engine: Engine, user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})


def _read_count(engine: Engine, user_id: int) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT failed_invite_attempts FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).scalar_one()


def test_concurrent_failed_invite_attempts_do_not_lose_updates(
    db_engine: Engine,
) -> None:
    user_id = _insert_test_user(db_engine)
    lock_acquired = threading.Event()
    release_a = threading.Event()
    session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )

    def connection_a() -> None:
        session_a = session_factory()
        try:
            user_a = session_a.get_one(User, user_id)
            register_failed_invite_attempt(session_a, user_a)
            lock_acquired.set()
            release_a.wait(timeout=5)
            session_a.commit()
        finally:
            session_a.close()

    def connection_b() -> None:
        session_b = session_factory()
        try:
            user_b = session_b.get_one(User, user_id)
            register_failed_invite_attempt(session_b, user_b)
            session_b.commit()
        finally:
            session_b.close()

    thread_a = threading.Thread(target=connection_a)
    thread_b = threading.Thread(target=connection_b)
    try:
        thread_a.start()
        assert lock_acquired.wait(timeout=5), (
            "La conexión A no adquirió el lock a tiempo"
        )

        thread_b.start()
        release_a.set()

        thread_a.join(timeout=5)
        thread_b.join(timeout=5)

        assert _read_count(db_engine, user_id) == 2, (
            "Ningún incremento debe perderse: +1 de A, +1 de B"
        )
    finally:
        release_a.set()
        if thread_a.is_alive():
            thread_a.join(timeout=5)
        if thread_b.is_alive():
            thread_b.join(timeout=5)
        _delete_test_user(db_engine, user_id)


def test_negative_control_without_for_update_loses_updates(db_engine: Engine) -> None:
    user_id = _insert_test_user(db_engine)
    session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )
    session_a = session_factory()
    session_b = session_factory()
    try:
        current_a = session_a.execute(
            text("SELECT failed_invite_attempts FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).scalar_one()
        current_b = session_b.execute(
            text("SELECT failed_invite_attempts FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).scalar_one()

        session_a.execute(
            text("UPDATE users SET failed_invite_attempts = :v WHERE id = :uid"),
            {"v": current_a + 1, "uid": user_id},
        )
        session_a.commit()

        session_b.execute(
            text("UPDATE users SET failed_invite_attempts = :v WHERE id = :uid"),
            {"v": current_b + 1, "uid": user_id},
        )
        session_b.commit()

        assert _read_count(db_engine, user_id) == 1, (
            "Lost update esperado sin FOR UPDATE, mismo razonamiento que 001"
        )
    finally:
        session_a.close()
        session_b.close()
        _delete_test_user(db_engine, user_id)
