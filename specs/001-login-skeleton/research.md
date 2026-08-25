# Phase 0 — Research: 001-login-skeleton

## 1. ORM y driver de PostgreSQL

**Decision**: SQLAlchemy 2.0 (estilo tipado, `Mapped[...]`/`mapped_column`) + `psycopg` v3 (driver
síncrono, paquete `psycopg[binary]`).

**Rationale**: `CLAUDE.md` ya fija Alembic como herramienta de migraciones, y Alembic autogenera
migraciones a partir de metadata de SQLAlchemy — son pareja estándar, no una decisión abierta en la
práctica. Se elige el modo síncrono (no `asyncio`) porque el volumen esperado es bajo (spec →
Assumptions: decenas de usuarios domésticos, sin concurrencia significativa); la complejidad de
gestionar sesiones async, pool async y `await` en cada acceso no está justificada por la escala
actual, y mantiene el código de `routers/login.py` más simple de leer y testear.

**Alternatives considered**:
- `asyncpg` + SQLAlchemy async: mayor throughput, pero complejidad operativa (event loop, sesiones
  async) sin beneficio medible al volumen de esta feature. Se revisaría si una feature futura
  introduce carga real que lo justifique.
- SQL crudo vía `psycopg` sin ORM: pierde el autogenerate de Alembic y el tipado de modelos que pide
  el Principio I de la constitución; obliga a escribir a mano cada `INSERT`/`UPDATE`/`SELECT`.

## 2. Librería de hashing de contraseña

**Decision**: `argon2-cffi`, algoritmo Argon2id, parámetros por defecto de la librería (ya calibrados
para uso interactivo de login).

**Rationale**: Argon2id es el ganador de la Password Hashing Competition y el algoritmo recomendado
actualmente por OWASP para almacenamiento de contraseñas — más resistente que bcrypt a ataques por
fuerza bruta acelerados por GPU. Coherente con la recomendación ya dada al usuario durante la
entrevista de requisitos (spec FR-003 acepta explícitamente "Argon2 o bcrypt"). `argon2-cffi` es la
implementación de referencia en Python (bindings sobre la librería C oficial), sin necesitar una capa
de abstracción adicional.

**Alternatives considered**:
- `bcrypt` (vía `passlib[bcrypt]` o `bcrypt` directo): más simple y con más historial de uso, pero
  más débil frente a ataques con hardware especializado (GPU/ASIC) que Argon2id. Válido igualmente
  según FR-003, pero Argon2id es la opción de mayor seguridad sin coste operativo adicional real.
- `passlib` como capa de abstracción sobre ambos: añade una dependencia con mantenimiento más lento
  que las librerías nativas; sin necesidad real de soportar múltiples algoritmos simultáneamente en
  esta feature (no hay migración de un hash legacy que soportar).

## 3. Estrategia de sesión de servidor

**Decision**: Token opaco no adivinable (`secrets.token_urlsafe(32)`, stdlib) generado en la capa de
aplicación al hacer login, persistido en `user_sessions.session_token` (PK `user_id`, ver
`data-model.md`), y entregado al navegador en una cookie `HttpOnly` + `Secure` (activada cuando la
petición entrante llega por HTTPS — detección por esquema de la petición, spec → Clarifications
2026-08-25) + `SameSite=Lax`. Cada request autenticado valida el token contra la fila de `user_sessions`
y comprueba `expires_at`; una petición válida desliza `expires_at` (ventana de 24h de inactividad,
spec → Assumptions).

**Rationale**: Decisión ya tomada explícitamente por el usuario en la entrevista de requisitos
("Sesión de servidor + cookie" frente a JWT). Un token opaco validado contra BD (no un JWT
autocontenido) es lo que permite invalidar de forma inmediata la sesión anterior de un usuario en
cuanto hace login en otro sitio (FR-004, sesión única) — con JWT habría que mantener una lista de
revocación de todas formas, perdiendo la ventaja de "sin estado" que en este caso no aporta nada.

**Alternatives considered**:
- JWT en cookie: descartado en la entrevista de requisitos; además no resuelve de forma nativa la
  invalidación inmediata de sesiones anteriores sin una lista de revocación adicional (que ya sería,
  en la práctica, el mismo `user_sessions`).
- `starlette.middleware.sessions.SessionMiddleware` (cookie firmada, sin estado en servidor): no
  permite invalidar una sesión desde el servidor sin cambiar la clave de firma global (afectaría a
  todos los usuarios), incompatible con FR-004.

## 4. Herramienta de migraciones

**Decision**: Alembic.

**Rationale**: No es una incógnita real de esta feature — ya está fijada en la sección "Comandos" de
`CLAUDE.md` (`uv run alembic upgrade head`, `uv run alembic revision --autogenerate`). Se documenta
aquí como decisión heredada, no como investigación abierta.

## 5. Estrategia de testing

**Decision**: `pytest` + `starlette.testclient.TestClient` (incluido con FastAPI) contra una base de
datos PostgreSQL de test real (mismo servicio `postgresql-x64-18` local, base de datos **separada**
de la de desarrollo — `TEST_DATABASE_URL` en `.env`, distinta de `DATABASE_URL`).

**Bootstrap del esquema de test** (resuelve Hallazgo F de `spec-critic`, 3ª pasada — ninguna tarea
creaba explícitamente la BD de test): una fixture de pytest `scope='session'`, `autouse=True` en
`tests/conftest.py` (`tasks.md` → T004) aplica las migraciones Alembic contra `TEST_DATABASE_URL`
una única vez al inicio de la suite, vía la API programática de Alembic
(`alembic.command.upgrade(cfg, "head")`) — no requiere un paso manual documentado aparte, ni que cada
desarrollador recuerde ejecutar `alembic upgrade head` contra la BD de test antes de correr `pytest`.

**Aislamiento entre tests**: la mayoría de los tests corren dentro de una transacción que se revierte
al finalizar (patrón savepoint sobre una única conexión, vía el fixture `db_session` de
`tests/conftest.py`), evitando estado compartido entre tests sin necesidad de recrear el esquema en
cada uno.

**Excepción — tests de concurrencia real** (p. ej. `tests/integration/test_lockout_concurrency.py`,
`tasks.md` → T033): el patrón savepoint-sobre-una-conexión de `db_session` es intencionadamente
*inadecuado* para probar locking a nivel de fila entre transacciones concurrentes — todas las
operaciones de un test comparten la misma conexión/transacción física, así que dos "sesiones" contra
ese fixture nunca contienden de verdad por un lock. Estos tests usan en su lugar un fixture distinto,
`db_engine` (motor SQLAlchemy crudo, sin envolver en la transacción compartida — ver `conftest.py`,
`tasks.md` → T004), para abrir dos conexiones genuinamente independientes, y limpian sus propios
datos de test explícitamente al final (no hay rollback automático fuera de `db_session`).

Además, "disparar dos hilos casi a la vez" **no es suficiente** para probar una condición de carrera
de forma determinista — el planificador del SO puede no solaparlos nunca, y el test pasaría igual con
o sin el lock (hallazgo detectado en la 3ª pasada de `spec-critic`: un test así sigue siendo, en la
práctica, un test de fachada intermitente). El patrón elegido en su lugar es **"bloqueo observado
directamente"**, en dos tests separados (ver `tests/integration/test_lockout_concurrency.py`,
`tasks.md` → T033):

- **Caso correcto** (con hilos reales): la conexión A abre transacción, ejecuta
  `register_failed_attempt` (adquiere `SELECT ... FOR UPDATE` internamente) y retiene
  deliberadamente el `commit()` hasta recibir una señal del hilo principal (`threading.Event`,
  nunca `sleep`/polling). El hilo principal solo lanza el hilo de la conexión B (que ejecuta la
  misma función) después de confirmar que A ya tiene el lock. A partir de ahí, Postgres serializa
  las dos escrituras por sí solo — no hace falta sincronización adicional para demostrar que el
  contador final es +2, sin incrementos perdidos.
- **Control negativo** (SIN hilos, interlineado manual): la variante sin `FOR UPDATE` **no** se
  prueba lanzando un segundo hilo y esperando que "gane la carrera" — eso sería, de nuevo, un test
  no determinista. En su lugar, el propio test interlinea las llamadas a propósito: A lee el valor,
  B lee el mismo valor viejo (una `SELECT` simple nunca se bloquea por el lock de otra transacción
  en PostgreSQL), A escribe y confirma, y B escribe sobre su lectura ya obsoleta y confirma —
  reproduciendo determinísticamente el lost update sin depender de qué hilo "gana".

**Corrección importante descubierta durante la implementación** (no detectada en ninguna de las 4
pasadas de `spec-critic`, que solo revisaron la especificación, no el comportamiento real de
Postgres): el diseño original proponía verificar el caso negativo con una variable compartida
`a_committed` que la conexión B comprobaba tras su propio `commit()`. Esa señal **no funciona**: en
PostgreSQL, la sentencia `UPDATE` de una fila bloquea contra el lock de esa fila tanto si hubo
`SELECT ... FOR UPDATE` antes como si no — el bloqueo de *escritura* no depende de esa cláusula, así
que B siempre acaba esperando al commit de A antes de poder escribir, con o sin `FOR UPDATE`. Lo que
realmente distingue los dos casos es qué *valor* leyó y escribió B, no si tuvo que esperar — por eso
el diseño final mide el contador final tras ambas escrituras, y usa interlineado manual (sin hilos)
para el control negativo en vez de depender de una carrera no determinista.

**Rationale**: Usar el mismo motor que producción evita falsos positivos/negativos por
comportamiento que SQLite u otro motor no reproduciría fielmente: índices funcionales
`LOWER(username)`, `CHECK` constraints, FK compuesta `(permission_level_group, permission_level_code)`
y el índice BRIN de `login_audit_log` son específicos de PostgreSQL.

**Alternatives considered**:
- SQLite en memoria para tests: mucho más rápido de arrancar, pero no soporta BRIN, difiere en
  colación de `LOWER()` para comparaciones case-insensitive, y no valida `CHECK`/FK compuestas de la
  misma forma — riesgo real de tests verdes que ocultan comportamiento roto en producción, inaceptable
  en un dominio financiero (Principio V de la constitución).

## 6. Rate limiting / lockout

**Decision**: Ya resuelto en el modelo de datos (`users.failed_login_attempts` + `users.locked_until`,
ver `data-model.md`) — no requiere infraestructura adicional (Redis descartado explícitamente por
`db-designer` para el volumen esperado de esta feature).
