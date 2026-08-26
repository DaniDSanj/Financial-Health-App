"""Test de concurrencia de consumo de código de invitación (T017, FR-006).

Patrón "bloqueo observado directamente" (igual que test_lockout_concurrency.py de
001): el propio `UPDATE household_invitations SET used_at=now(), used_by=:user_id
WHERE id=:id AND used_at IS NULL` de `consume_invitation()` adquiere el lock de
fila — Postgres serializa la segunda conexión sin necesitar sincronización
adicional más allá de forzar el orden de arranque con threading.Event.
"""

import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from financial_health_app.auth.invite_code import hash_code
from financial_health_app.models.household import Household
from financial_health_app.models.household_invitation import HouseholdInvitation
from financial_health_app.models.user import User
from financial_health_app.routers.household import consume_invitation


def _setup(engine: Engine) -> tuple[int, int, int]:
    """Crea un hogar, un usuario propietario, un segundo usuario consumidor, y una
    invitación vigente. Devuelve (invitation_id, consumer_id, owner_id)."""
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        owner = User(
            username="concurrency-invite-owner",
            email="concurrency-invite-owner@example.com",
            password_hash="dummy-hash",
            first_name="Owner",
            permission_level_code="ADM",
        )
        session.add(owner)
        session.flush()

        household = Household(name="Hogar concurrencia", created_by=owner.id)
        session.add(household)
        session.flush()
        owner.household_id = household.id

        consumer = User(
            username="concurrency-invite-consumer",
            email="concurrency-invite-consumer@example.com",
            password_hash="dummy-hash",
            first_name="Consumer",
            permission_level_code="MEM",
        )
        session.add(consumer)
        session.flush()

        invitation = HouseholdInvitation(
            household_id=household.id,
            code_hash=hash_code("ABCD2345"),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
            created_by=owner.id,
        )
        session.add(invitation)
        session.flush()

        session.commit()
        return invitation.id, consumer.id, owner.id
    finally:
        session.close()


def _cleanup(
    engine: Engine, *, invitation_id: int, consumer_id: int, owner_id: int
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET household_id = NULL WHERE id IN (:o, :c)"),
            {"o": owner_id, "c": consumer_id},
        )
        conn.execute(
            text("DELETE FROM household_invitations WHERE id = :id"),
            {"id": invitation_id},
        )
        conn.execute(
            text("DELETE FROM households WHERE created_by = :o"), {"o": owner_id}
        )
        conn.execute(
            text("DELETE FROM users WHERE id IN (:o, :c)"),
            {"o": owner_id, "c": consumer_id},
        )


def test_concurrent_consumption_only_one_succeeds(db_engine: Engine) -> None:
    invitation_id, consumer_id, owner_id = _setup(db_engine)
    lock_acquired = threading.Event()
    release_a = threading.Event()
    session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )
    results: dict[str, bool] = {}

    def connection_a() -> None:
        session_a = session_factory()
        try:
            won_a = consume_invitation(
                session_a, invitation_id=invitation_id, user_id=consumer_id
            )
            results["a"] = won_a
            lock_acquired.set()
            release_a.wait(timeout=5)
            session_a.commit()
        finally:
            session_a.close()

    def connection_b() -> None:
        session_b = session_factory()
        try:
            won_b = consume_invitation(
                session_b, invitation_id=invitation_id, user_id=consumer_id
            )
            results["b"] = won_b
            session_b.commit()
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
        assert outcomes.count(True) == 1 and outcomes.count(False) == 1, (
            f"Se esperaba exactamente un ganador y un perdedor, se obtuvo {outcomes}"
        )

        with db_engine.connect() as conn:
            used_by = conn.execute(
                text("SELECT used_by FROM household_invitations WHERE id = :id"),
                {"id": invitation_id},
            ).scalar_one()
        assert used_by == consumer_id
    finally:
        release_a.set()
        if thread_a.is_alive():
            thread_a.join(timeout=5)
        if thread_b.is_alive():
            thread_b.join(timeout=5)
        _cleanup(
            db_engine,
            invitation_id=invitation_id,
            consumer_id=consumer_id,
            owner_id=owner_id,
        )
