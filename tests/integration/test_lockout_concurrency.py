"""Test de concurrencia determinista del lockout (T033).

Patrón: "bloqueo observado directamente". No usa db_session (rollback compartido sobre
una única conexión, inadecuado para probar locking real entre transacciones) sino
db_engine (conexiones genuinamente independientes) — ver research.md §5.

Nota sobre el diseño (hallazgo empírico durante la implementación, corrige la
especificación original de T033/tasks.md): en PostgreSQL, la sentencia UPDATE de una
fila bloquea contra el lock de esa fila tanto si la sesión hizo SELECT ... FOR UPDATE
antes como si no — el bloqueo de escritura no depende de esa cláusula, así que "¿la
escritura de B esperó al commit de A?" NO distingue el caso correcto del incorrecto (en
ambos casos B acaba esperando). La señal real de un "lost update" es qué VALOR lee y
escribe B: una SELECT sin FOR UPDATE no se bloquea por el lock de A, así que B puede
leer el valor viejo mientras A todavía no ha confirmado, y calcular su escritura sobre
ese dato obsoleto — aunque la propia escritura de B se retrase hasta después del commit
de A. Por eso:

- Caso CORRECTO (con FOR UPDATE): dos hilos genuinamente concurrentes. La propia
  serialización de Postgres basta para que B siempre lea el valor ya actualizado por A,
  sin necesitar sincronización adicional en el test.
- Caso NEGATIVO (sin FOR UPDATE): requiere forzar explícitamente que la lectura de B
  ocurra mientras A todavía retiene el lock (antes de su commit) — si no, el resultado
  depende de una carrera no determinista entre el hilo de A y el de B. Por eso el
  control negativo no usa hilos: interlinea las llamadas a propósito desde el hilo
  principal del test.
"""

import threading

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from financial_health_app.auth.lockout import register_failed_attempt
from financial_health_app.models.user import User


def _insert_test_user(engine: Engine) -> int:
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        user = User(
            username="concurrency-test-user",
            email="concurrency-test-user@example.com",
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
        conn.execute(
            text("DELETE FROM login_audit_log WHERE user_id = :uid"), {"uid": user_id}
        )
        conn.execute(
            text("DELETE FROM user_sessions WHERE user_id = :uid"), {"uid": user_id}
        )
        conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})


def _read_count(engine: Engine, user_id: int) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT failed_login_attempts FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).scalar_one()


def test_concurrent_failed_attempts_do_not_lose_updates(db_engine: Engine) -> None:
    """Caso correcto: dos hilos genuinamente concurrentes, ambos usando
    register_failed_attempt (con SELECT ... FOR UPDATE). Postgres serializa las
    escrituras por sí solo — sin necesitar sincronización adicional en el test más allá
    de arrancar ambos hilos tras confirmar que A ya tiene el lock.
    """
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
            register_failed_attempt(
                session_a, user_a
            )  # adquiere FOR UPDATE internamente
            lock_acquired.set()
            release_a.wait(timeout=5)
            session_a.commit()
        finally:
            session_a.close()

    def connection_b() -> None:
        session_b = session_factory()
        try:
            user_b = session_b.get_one(User, user_id)
            register_failed_attempt(session_b, user_b)
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
    """Control negativo (paso 5 de T033): mismo patrón leer-incrementar-escribir, SIN
    `FOR UPDATE`. Interlineado manual y explícito (sin hilos) para forzar de forma
    determinista que B lea el valor viejo mientras A todavía no ha confirmado —
    precisamente la condición que SELECT ... FOR UPDATE existe para impedir. Sin este
    interlineado forzado, el resultado dependería de una carrera no determinista entre
    hilos (ver nota del módulo).
    """
    user_id = _insert_test_user(db_engine)
    session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )
    session_a = session_factory()
    session_b = session_factory()
    try:
        # A: lee el valor actual (0) pero NO confirma todavía.
        current_a = session_a.execute(
            text("SELECT failed_login_attempts FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).scalar_one()

        # B: lee el MISMO valor viejo (0) — una SELECT simple no se bloquea por nada
        # de A, porque A ni siquiera tomó FOR UPDATE en este escenario negativo.
        current_b = session_b.execute(
            text("SELECT failed_login_attempts FROM users WHERE id = :uid"),
            {"uid": user_id},
        ).scalar_one()

        # A escribe y confirma su incremento.
        session_a.execute(
            text("UPDATE users SET failed_login_attempts = :v WHERE id = :uid"),
            {"v": current_a + 1, "uid": user_id},
        )
        session_a.commit()

        # B escribe sobre el valor que ya tenía leído (obsoleto) y confirma —
        # sobrescribe el incremento de A con el suyo propio, calculado sobre datos
        # viejos.
        session_b.execute(
            text("UPDATE users SET failed_login_attempts = :v WHERE id = :uid"),
            {"v": current_b + 1, "uid": user_id},
        )
        session_b.commit()

        assert _read_count(db_engine, user_id) == 1, (
            "Lost update esperado: B calculó su escritura sobre el valor leído antes "
            "del commit de A, así que el incremento de A se pierde — exactamente lo "
            "que SELECT ... FOR UPDATE existe para evitar, forzando a B a leer el "
            "valor ya actualizado por A antes de calcular el suyo."
        )
    finally:
        session_a.close()
        session_b.close()
        _delete_test_user(db_engine, user_id)
