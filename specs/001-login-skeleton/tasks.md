# Tasks: Esqueleto de login y modelo de datos base

**Input**: Design documents from `specs/001-login-skeleton/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/login.md, quickstart.md

**Tests**: Obligatorios per constitución Principio III (Test-First Estricto). Lógica de negocio de
seguridad (hashing, sesión, lockout, **registro de auditoría FR-012**) exige TDD estricto: test
escrito y en rojo antes de la implementación. El resto de tareas exige al menos un test antes de
cerrarse, sin requerir orden TDD estricto.

**Organization**: Tareas agrupadas por user story (US1/US2/US3, prioridad P1/P2/P3 de `spec.md`) para
permitir implementación y verificación independientes de cada una.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (ficheros distintos, sin dependencias pendientes)
- **[Story]**: A qué user story pertenece (US1, US2, US3) — solo en fases 3-5
- Cada tarea incluye la ruta exacta del fichero a crear/modificar

## Path Conventions

Proyecto único (ver `plan.md` → Project Structure): `src/financial_health_app/`, `alembic/`, `tests/`,
`scripts/` en la raíz del repo.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialización del proyecto y estructura básica.

- [X] T001 Crear estructura de directorios `src/financial_health_app/{models,auth,routers,templates}/`,
  `alembic/`, `tests/{unit,integration}/`, con los `__init__.py` correspondientes, per `plan.md` →
  Project Structure.
- [X] T002 [P] Añadir dependencias de producción: `uv add sqlalchemy "psycopg[binary]" argon2-cffi alembic`
  (actualiza `pyproject.toml` y `uv.lock`).
- [X] T003 [P] Scaffolding de Alembic: `alembic.ini` en la raíz del repo, `alembic/env.py` leyendo la
  URL de conexión desde `config.get_main_option("sqlalchemy.url")` en vez de leer `DATABASE_URL`
  directamente del entorno — de forma que, si el llamador (T004) hace
  `cfg.set_main_option("sqlalchemy.url", ...)` antes de invocar Alembic programáticamente, `env.py`
  respeta ese valor en vez de ignorarlo; si no se sobrescribe, el `alembic.ini`/CLI por defecto sigue
  leyendo `DATABASE_URL` de `.env` para el uso manual (`uv run alembic upgrade head`). Usa
  `target_metadata` de la Base declarativa de `src/financial_health_app/db.py` (se crea en T005).
  Resuelve Hallazgo nuevo #5 de la 4ª pasada de `spec-critic`: sin este contrato explícito entre
  T003/T004, la fixture de test podría migrar silenciosamente la BD de desarrollo en vez de la de
  test.
- [X] T004 [P] `tests/conftest.py`, tres piezas:
  (a) fixture de sesión de pytest (`scope='session'`, `autouse=True`) que construye la configuración
  de Alembic, sobrescribe explícitamente `cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)`
  (T003 garantiza que `env.py` respeta este override) y aplica las migraciones contra esa base de
  datos de test **separada** (`TEST_DATABASE_URL` en `.env`, distinta de `DATABASE_URL` de
  desarrollo) una única vez antes de que corra cualquier test, usando la API programática de Alembic
  (`alembic.command.upgrade(cfg, "head")`) — sin esta pieza, la suite asume un esquema que nadie crea
  explícitamente (resuelve Hallazgo F de `spec-critic`, 3ª pasada);
  (b) fixture `db_session` — sesión de base de datos de test contra esa misma BD, con rollback tras
  cada test (patrón savepoint sobre una única conexión — ver `research.md` §5);
  (c) fixture `db_engine` — motor SQLAlchemy crudo, sin envolver en la transacción compartida, para
  el test de concurrencia T033, que necesita conexiones genuinamente independientes y limpia sus
  propios datos de test explícitamente (sin rollback automático fuera de `db_session`).

**Checkpoint**: Estructura de proyecto lista, dependencias instaladas.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestructura común que TODAS las user stories necesitan.

**⚠️ CRITICAL**: Ninguna user story puede empezar hasta que esta fase esté completa.

- [X] T005 `src/financial_health_app/db.py`: Base declarativa de SQLAlchemy 2.0, `engine`,
  `sessionmaker`, dependencia FastAPI `get_db()`.
- [X] T006 [P] Modelo `KeysCatalog` en `src/financial_health_app/models/keys_catalog.py` — columnas y
  constraints exactos de `data-model.md` → `keys_catalog` (`UNIQUE(group_code, code)`, índice
  `group_code`, campos de auditoría completos).
- [X] T007 [P] Modelo `Household` en `src/financial_health_app/models/household.py` — per
  `data-model.md` → `households`.
- [X] T008 [P] Modelo `User` en `src/financial_health_app/models/user.py` — per `data-model.md` →
  `users` (incluye `failed_login_attempts`, `locked_until`, FK compuesta a `keys_catalog`, índices
  funcionales `LOWER(username)`/`LOWER(email)`).
- [X] T009 [P] Modelo `UserSession` en `src/financial_health_app/models/user_session.py` — per
  `data-model.md` → `user_sessions` (PK = `user_id`, sin `created_by`/`updated_by`/`version`).
- [X] T010 [P] Modelo `LoginAuditLog` en `src/financial_health_app/models/login_audit_log.py` — per
  `data-model.md` → `login_audit_log` (`result` CHECK IN success/failure/locked, índice BRIN sobre
  `occurred_at`).
- [X] T011 Migración Alembic inicial en `alembic/versions/` que crea las 5 tablas en el orden de
  `data-model.md` → "Orden de creación" (keys_catalog/households sin FK de auditoría → users →
  user_sessions/login_audit_log → ALTER TABLE añadiendo las FK de auditoría pendientes) y siembra el
  grupo `NUS` en `keys_catalog`. Depende de T006–T010.
- [X] T012 [P] Test de integración: `alembic upgrade head` crea las 5 tablas y siembra el grupo `NUS`
  correctamente, en `tests/integration/test_migration.py` (test mínimo obligatorio para una tarea no
  de lógica de negocio, per constitución Principio III).
- [X] T013 `src/financial_health_app/main.py`: app factory de FastAPI, montaje de `Jinja2Templates`
  apuntando a `templates/`.
- [X] T014 [P] Test de integración: con la cabecera `X-Forwarded-Proto: https` enviada desde un origen
  de confianza, `request.url.scheme` (y por tanto el criterio de cookie `Secure`) resuelve a `https`;
  sin esa cabecera se mantiene `http` — en `tests/integration/test_proxy_headers.py`. Escribir y
  comprobar que falla antes de T015 (resuelve Hallazgo 7 de `spec-critic`: la app se desplegará
  detrás de un proxy inverso/balanceador que termina TLS).
- [X] T015 Configurar detección de HTTPS detrás de proxy inverso en `main.py`:
  `ProxyHeadersMiddleware` de Starlette (o `--proxy-headers`/`--forwarded-allow-ips` de uvicorn),
  confiando únicamente en los proxies configurados como de confianza. La lista de proxies de
  confianza se lee de la variable de entorno `TRUSTED_PROXY_IPS` en `.env` (mismo patrón que
  `DATABASE_URL`) — cambiarla no requiere tocar código ni redeploy, solo configuración por entorno
  (resuelve Hallazgo H de la 3ª pasada de `spec-critic`). Con esto, `request.url.scheme` refleja
  HTTPS real cuando el proxy termina TLS y reenvía por HTTP interno. Depende de T013, T014.
- [X] T016 [P] `src/financial_health_app/templates/base.html`: layout compartido (bloques para título y
  contenido).
- [X] T017 [P] Test unitario de `record_login_attempt(db, user_id, identifier, result)`: escribe
  correctamente una fila en `login_audit_log` para cada valor de `result`
  (`success`/`failure`/`locked`), en `tests/unit/test_audit.py`. Escribir y comprobar que falla antes
  de T018 (TDD estricto — FR-012 es lógica de seguridad, resuelve Hallazgo 3 de `spec-critic`: el
  test de auditoría debe preceder a su implementación, no venir después en las fases de user story).
- [X] T018 `src/financial_health_app/auth/audit.py`: `record_login_attempt(db, user_id, identifier,
  result)` que escribe una fila en `login_audit_log` (resultado `success`/`failure`/`locked`, per
  FR-012); usado por las 3 user stories. Depende de T017.

**Checkpoint**: Fundamentos listos — puede empezar la implementación de cualquier user story.

---

## Phase 3: User Story 1 - Login con credenciales válidas (Priority: P1) 🎯 MVP

**Goal**: Un usuario ya existente inicia sesión con username/email + password y llega a una página de
bienvenida; puede cerrar sesión; sin sesión activa no accede a la bienvenida.

**Independent Test**: Con un usuario de prueba ya insertado, acceder a `/login`, introducir
credenciales correctas y comprobar que se llega a la página de bienvenida con su nombre real
(quickstart.md, escenario 1).

### Tests for User Story 1 (obligatorio per constitución Principio III) ⚠️

> **NOTA: escribir estos tests PRIMERO, comprobar que fallan antes de implementar**

- [X] T019 [P] [US1] Test unitario de `hash_password`/`verify_password` (round-trip, hash no
  reversible) en `tests/unit/test_hashing.py`. Incluye: verificar que
  `verify_password_timing_safe(password, hash_or_none=None)` (mitigación de enumeración por timing,
  ver T022) ejecuta igualmente una verificación Argon2id completa contra un hash dummy precalculado y
  devuelve `False`, sin atajos que la hagan más rápida que una verificación real (resuelve Hallazgo 2
  de `spec-critic`, SC-002).
- [X] T020 [P] [US1] Test de integración de los Acceptance Scenarios 1–3 de US1 (login correcto →
  bienvenida con nombre real; logout → invalida sesión y redirige a login; sin sesión → redirige a
  login) en `tests/integration/test_login_flow.py`. Incluye: (a) verificar que un login correcto
  escribe una fila en `login_audit_log` con `result='success'` (FR-012); (b) verificar que el login
  con el identificador en distinta capitalización (p. ej. `JDoe`/`JDOE@example.com`) resuelve al
  mismo usuario (FR-010).

### Implementation for User Story 1

- [X] T021 [P] [US1] `src/financial_health_app/auth/hashing.py`: `hash_password`/`verify_password` con
  Argon2id vía `argon2-cffi` (FR-003, ADR-0002); además `verify_password_timing_safe(password: str,
  hash_or_none: str | None) -> bool`, que si `hash_or_none` es `None` (usuario inexistente) verifica
  igualmente contra un hash dummy precalculado a nivel de módulo y devuelve `False`, para que el
  coste computacional sea equivalente al de una verificación real (mitigación de enumeración de
  usuarios por timing — SC-002, ADR-0004).
- [X] T022 [P] [US1] `src/financial_health_app/auth/session.py`: `create_session` (UPSERT en
  `user_sessions`, invalida cualquier sesión anterior del mismo usuario — FR-004), `validate_session`,
  `invalidate_session`; ventana de expiración de 24h deslizante sobre cualquier request autenticado
  (spec → Clarifications 2026-08-25).
- [X] T023 [US1] `src/financial_health_app/templates/login.html`: formulario con campos `identifier` y
  `password` (extiende `base.html`).
- [X] T024 [US1] `src/financial_health_app/templates/welcome.html`: muestra `first_name` del usuario
  autenticado (FR-008) y botón/formulario que envía `POST /logout` (FR-009).
- [X] T025 [US1] `src/financial_health_app/routers/login.py`: `GET /login`, `POST /login` (camino de
  éxito: valida credenciales, crea sesión, registra auditoría `success`, fija cookie
  `HttpOnly`+`Secure` si HTTPS+`SameSite=Lax`), `POST /logout`, `GET /` — per `contracts/login.md`.
  Depende de T021, T022, T018, T023, T024.
- [X] T026 [US1] Montar el router de login en `main.py` (depende de T013, T015, T025).

**Checkpoint**: User Story 1 funcional y verificable de forma independiente (camino feliz E2E).

---

## Phase 4: User Story 2 - Rechazo de credenciales inválidas (Priority: P2)

**Goal**: Password o identificador incorrectos muestran un único mensaje de error genérico, sin crear
sesión ni revelar cuál campo falló ni si el identificador existe (ni por contenido del mensaje ni por
tiempo de respuesta).

**Independent Test**: Con el mismo usuario de prueba, introducir una contraseña incorrecta y verificar
error genérico sin sesión creada (quickstart.md, escenario 2).

### Tests for User Story 2 (obligatorio per constitución Principio III) ⚠️

- [X] T027 [P] [US2] Test de integración: password incorrecta e identificador inexistente devuelven el
  mismo mensaje de error genérico y no crean sesión (FR-006, SC-002) en
  `tests/integration/test_login_flow.py`. Incluye: (a) verificar que cada intento fallido escribe una
  fila en `login_audit_log` con `result='failure'` (FR-012); (b) verificar, vía mock/spy sobre
  `auth.hashing.verify_password`/`verify_password_timing_safe` (no medición de reloj real, para
  evitar un test inestable en CI), que la ruta de identificador inexistente invoca la verificación
  contra el hash dummy exactamente igual que la ruta de password incorrecta contra un usuario real —
  mitigación de enumeración por timing (Hallazgo 2 de `spec-critic`, SC-002).
- [X] T028 [US2] Test de integración: formulario con campos vacíos devuelve `422` sin consultar la
  base de datos, en `tests/integration/test_login_flow.py` (sin `[P]`: comparte fichero con T027).

### Implementation for User Story 2

- [X] T029 [US2] Extender `POST /login` en `src/financial_health_app/routers/login.py` con la rama de
  fallo: identificador no existe o password incorrecta → mensaje de error genérico único (FR-006), sin
  crear sesión, registrando auditoría `failure` vía `auth/audit.py`. Cuando el identificador no
  existe, invocar igualmente `verify_password_timing_safe(password, None)` (T021) antes de responder,
  para no crear una diferencia de tiempo observable frente al caso de password incorrecta contra un
  usuario real. Depende de T025, T018, T021.
- [X] T030 [US2] Validación de campos vacíos en `POST /login` (respuesta `422`, re-render del
  formulario) antes de consultar la base de datos.

**Checkpoint**: User Stories 1 y 2 funcionan de forma independiente.

---

## Phase 5: User Story 3 - Bloqueo temporal tras intentos fallidos repetidos (Priority: P3)

**Goal**: Tras 5 fallos consecutivos contra un mismo usuario, el sistema bloquea nuevos intentos
durante 15 minutos, con reseteo automático del contador al expirar, sin perder incrementos aunque
lleguen intentos fallidos casi simultáneos.

**Independent Test**: Introducir 5 contraseñas incorrectas seguidas y comprobar que el 6º intento
(aunque la contraseña sea correcta) es rechazado por bloqueo (quickstart.md, escenario 3).

### Tests for User Story 3 (obligatorio per constitución Principio III) ⚠️

- [X] T031 [P] [US3] Test unitario de `lockout.py`: 5 fallos consecutivos activan el bloqueo de 15
  minutos, el intento 6º se rechaza por bloqueo, y el contador se resetea automáticamente al expirar
  sin requerir login correcto previo (FR-007, SC-003), en `tests/unit/test_lockout.py`.
- [X] T032 [P] [US3] Test de integración del escenario de bloqueo completo end-to-end (5 fallos → 6º
  intento bloqueado → expiración → reseteo automático → login correcto), en
  `tests/integration/test_login_flow.py`. Incluye: verificar que el 6º intento (rechazado por
  bloqueo, sin llegar a verificar password) escribe en `login_audit_log` con `result='locked'`,
  distinto de `'failure'` (FR-012).
- [X] T033 [P] [US3] Test de concurrencia determinista ("bloqueo observado directamente") en
  `tests/integration/test_lockout_concurrency.py`, usando el fixture `db_engine` de T004 (NO el
  `db_session` de rollback compartido — no ejerce contención real). Diseño final (dos tests,
  **corregido durante la implementación** respecto a la especificación previa a `spec-critic` 4ª
  pasada — ver nota abajo):
  1. `test_concurrent_failed_attempts_do_not_lose_updates` (caso correcto, con hilos reales): A
     abre transacción, ejecuta `register_failed_attempt` (adquiere `SELECT ... FOR UPDATE`
     internamente), señala `lock_acquired`, espera `release_a` antes de hacer commit. El hilo
     principal espera `lock_acquired.wait()` (no `sleep`/polling) antes de lanzar el hilo de B, que
     ejecuta la misma `register_failed_attempt`. Postgres serializa las dos escrituras por sí solo
     — no hace falta sincronizar más. Se verifica que el contador final es exactamente +2.
  2. `test_negative_control_without_for_update_loses_updates` (control negativo, SIN hilos):
     interlineado manual y explícito desde el hilo principal del test — A lee el valor, B lee el
     mismo valor viejo (una SELECT simple nunca se bloquea), A escribe y confirma, B escribe sobre
     su lectura obsoleta y confirma. Se verifica que el contador final es 1 (lost update).
  Ambos tests envueltos en `try/finally` para limpieza garantizada de datos y conexiones aunque
  una aserción falle a mitad de test.

  **Nota — corrección respecto al diseño original**: la especificación previa a la implementación
  (basada en una variable compartida `a_committed` observada por B tras su propio commit) resultó
  técnicamente inválida: en PostgreSQL, la sentencia `UPDATE` de una fila bloquea contra el lock de
  esa fila tanto si hubo `SELECT ... FOR UPDATE` antes como si no — el bloqueo de escritura no
  depende de esa cláusula, así que "¿la escritura de B esperó al commit de A?" NO distingue el caso
  correcto del incorrecto (en ambos casos B acaba esperando). Verificado empíricamente: el test
  negativo con ese mecanismo pasaba con `a_committed=True` en ambas variantes. La señal real de un
  "lost update" es el VALOR final tras ambas escrituras, no si la escritura de B esperó — por eso
  el diseño final mide el contador final, y el control negativo fuerza el interlineado
  explícitamente (sin hilos) en vez de depender de una carrera no determinista entre hilos para el
  caso sin `FOR UPDATE`. Ver `research.md` §5 para el detalle completo y el razonamiento.
  Resuelve Hallazgo 6 original y Hallazgo A de la 2ª/3ª/4ª pasada de `spec-critic` (CHK003).

### Implementation for User Story 3

- [X] T034 [US3] `src/financial_health_app/auth/lockout.py`: `check_lockout(user)`,
  `register_failed_attempt(db, user)`. Implementación explícitamente en patrón
  leer-incrementar-escribir (no un `UPDATE ... SET failed_login_attempts = failed_login_attempts + 1`
  atómico de una sola sentencia): `SELECT ... FOR UPDATE` sobre la fila del usuario, leer el valor
  actual de `failed_login_attempts` en Python, decidir si se alcanza el umbral de 5 (y en tal caso
  fijar `locked_until`), y escribir el nuevo valor de vuelta — el `SELECT ... FOR UPDATE` es
  necesario precisamente porque la decisión de bloquear depende de leer el valor antes de escribirlo
  (a diferencia de un incremento atómico, que Postgres ya serializa por sí solo sin necesitar la
  cláusula). Debe satisfacer el test de concurrencia T033, incluida su variante negativa (mismo
  patrón, sin `FOR UPDATE`, debe fallar). Lógica de reseteo automático del contador al expirar
  `locked_until`.
- [X] T035 [US3] Integrar `lockout.py` en `POST /login` (`src/financial_health_app/routers/login.py`):
  comprobar bloqueo antes de verificar la contraseña, incrementar/bloquear en fallo, resetear en éxito,
  registrar auditoría `locked` (distinta de `failure`) vía `auth/audit.py`. Depende de T025, T029,
  T034, T018.

**Checkpoint**: Las 3 user stories son funcionales e independientemente verificables.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mejoras transversales y cierre de gaps diferidos desde `checklists/security.md`. Cada
tarea de implementación lleva su test asociado ANTES en la numeración (Principio III: ninguna tarea
se cierra sin al menos un test, sin excepción por ser fase de Polish — resuelve Hallazgo 1 de
`spec-critic`).

### Tests for Polish (obligatorio per constitución Principio III) ⚠️

- [X] T036 [P] Test: `login.html` renderiza `autocomplete="off"` en el campo password, en
  `tests/integration/test_templates.py`.
- [X] T037 [P] Test: un fallo simulado de base de datos durante `POST /login` (mock de la sesión de
  BD lanzando una excepción) devuelve una página de error genérica, sin filtrar stacktrace ni detalle
  interno en el cuerpo de la respuesta, en `tests/integration/test_error_handling.py`.
- [X] T038 [P] Test: `scripts/seed_user.py` hashea correctamente la contraseña dada e inserta un
  usuario que después puede autenticarse con éxito vía el flujo real de `POST /login`, en
  `tests/integration/test_seed_script.py`.
- [X] T039 [P] Test: `scripts/purge_login_audit_log.py` borra únicamente las filas de
  `login_audit_log` con `occurred_at` de más de 90 días, retiene las de 90 días o menos, y trata
  correctamente el caso límite exacto de 90 días, en `tests/integration/test_purge_script.py`.

### Implementation for Polish

- [X] T040 [P] Añadir `autocomplete="off"` al campo password en `login.html` (CHK019). Depende de
  T036.
- [X] T041 [P] Handler de error genérico en `main.py` ante fallo de base de datos durante el login
  (sin filtrar detalles internos/stacktrace al usuario) (CHK016). Depende de T037.
- [X] T042 [P] `scripts/seed_user.py`: script que hashea una contraseña con `argon2-cffi` e inserta el
  usuario de prueba (reemplaza el placeholder manual de hash en `quickstart.md`) (CHK001). Depende de
  T038.
- [X] T043 [P] `scripts/purge_login_audit_log.py`: borra filas de `login_audit_log` con más de 90 días
  de antigüedad (FR-012); documentar en el propio script que la programación periódica (cron) es un
  paso operativo fuera del alcance de esta feature (CHK004/CHK005). Depende de T039.
- [X] T044 `uv run ruff check --fix src/` + `uv run ruff format src/` + `uv run ty check` sobre todo
  `src/` y `tests/`.
- [X] T045 Ejecutar el guion UAT completo de `quickstart.md` (5 escenarios). Incluye registrar
  manualmente el tiempo observado entre el envío del formulario de login y el renderizado completo de
  la página de bienvenida, verificando SC-001 (<3s) — sin tarea automatizada dedicada dado el volumen
  doméstico esperado (spec.md → Assumptions), pero con verificación explícita en UAT en vez de
  quedar implícita (corregido tras 2ª pasada de `spec-critic`, Hallazgo D). **No marcar esta tarea
  como Done sin confirmación humana explícita** — flujo user-facing, UAT obligatoria per
  `01_estilo_comportamiento.md` §3.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias — puede empezar de inmediato.
- **Foundational (Phase 2)**: depende de Setup — bloquea todas las user stories.
- **User Stories (Phase 3+)**: todas dependen de que Foundational esté completa.
  - US1 no depende de otras historias.
  - US2 extiende el mismo `routers/login.py` que crea US1 (T025) — requiere US1 implementada primero
    a nivel de código, pero es verificable de forma independiente por sus propios Acceptance Scenarios.
  - US3 igualmente extiende `routers/login.py` (tras US1/US2) e introduce su propio módulo
    `lockout.py`, independientemente testeable.
- **Polish (Final Phase)**: depende de que las user stories deseadas estén completas.

### Within Each User Story / Fase

- Tests (obligatorios) se escriben y deben fallar ANTES de la implementación — incluida la fase de
  Polish (T036-T039 antes de T040-T043).
- Modelos (Foundational) antes que servicios de auth.
- Servicios de auth (`hashing.py`, `session.py`, `lockout.py`, `audit.py`) antes que el router.
- El test de auditoría (T017) precede a su implementación (T018), no viene después como parte de las
  fases de user story.
- Implementación core antes que integración entre historias.

### Parallel Opportunities

- T002, T003, T004 (Setup) en paralelo.
- T006–T010 (modelos, Foundational) en paralelo.
- T014 (test proxy) y T017 (test auditoría) en paralelo entre sí.
- T019, T020 (tests US1) en paralelo; T021, T022 (implementación US1) en paralelo.
- T027 puede ejecutarse en paralelo con tareas de otras fases sin dependencia; T028 NO es paralelo a
  T027 (comparten `tests/integration/test_login_flow.py` — corregido tras 2ª pasada de `spec-critic`,
  Hallazgo C).
- T031, T032, T033 (tests US3) en paralelo.
- T036–T039 (tests Polish) en paralelo; T040–T043 (implementación Polish) en paralelo.

---

## Parallel Example: User Story 1

```bash
# Tests de US1 en paralelo:
Task: "Test unitario hash_password/verify_password (+ verify_password_timing_safe) en tests/unit/test_hashing.py"
Task: "Test de integración login/logout/redirect en tests/integration/test_login_flow.py"

# Implementación de US1 en paralelo:
Task: "auth/hashing.py: hash_password/verify_password/verify_password_timing_safe con Argon2id"
Task: "auth/session.py: create_session/validate_session/invalidate_session"
```

---

## Implementation Strategy

### MVP First (User Story 1 solamente)

1. Completar Phase 1: Setup.
2. Completar Phase 2: Foundational (CRÍTICO — bloquea todas las historias).
3. Completar Phase 3: User Story 1.
4. **PARAR y VALIDAR**: probar User Story 1 de forma independiente (login → bienvenida → logout).
5. Demo si está listo.

### Incremental Delivery

1. Setup + Foundational → base lista.
2. + User Story 1 → validar de forma independiente → MVP.
3. + User Story 2 → validar de forma independiente.
4. + User Story 3 → validar de forma independiente.
5. + Polish → UAT completa (T045) antes de `/speckit.converge`.

---

## Notes

- [P] = ficheros distintos, sin dependencias entre sí.
- [Story] mapea la tarea a su user story para trazabilidad.
- Verificar que los tests fallan antes de implementar (TDD, Principio III de la constitución) —
  incluida la fase de Polish, sin excepción.
- Los puntos diferidos por `checklists/security.md` a esta fase quedan resueltos en tareas concretas:
  CHK001→T042, CHK003→T034 (con test de concurrencia T033), CHK004/CHK005→T043, CHK016→T041,
  CHK019→T040. CHK002 no genera tarea (confirmado N/A, sin borrado de usuarios en el alcance de esta
  feature).
- No se cierra T045 sin confirmación humana explícita (UAT).
- **2026-08-25 (`/speckit.analyze`)**: resueltos los hallazgos C1 (CRITICAL — T015/FR-012 sin test
  asociado, violaba Principio III NON-NEGOTIABLE) y C2 (MEDIUM — FR-010 sin test de
  case-insensitividad) extendiendo los tests de US1/US2/US3 con aserciones explícitas sobre
  `login_audit_log` y sobre la comparación insensible a mayúsculas/minúsculas. F1 y F2
  (inconsistencias de redacción/estructura) resueltos en `research.md`, `contracts/login.md` y
  `plan.md`.
- **2026-08-25 (`spec-critic`, veredicto NO-GO, resuelto)**: renumerada toda la fase de Polish para
  que cada tarea de implementación tenga su test antes (Hallazgo 1); añadidos T021/T029 (mitigación de
  enumeración por timing en login, Hallazgo 2, documentada en ADR-0004); movido el test de auditoría
  (T017) antes de su implementación (T018, antes T015) para respetar TDD estricto (Hallazgo 3);
  añadido T033 (test de concurrencia real para el lockout, Hallazgo 6); añadidos T014/T015
  (configuración de detección de HTTPS detrás de proxy inverso, Hallazgo 7 — confirmado con el humano
  que la app se desplegará detrás de uno). Hallazgos 4 y 5 (ADR-0002 con lenguaje obsoleto y
  `plan.md` desincronizado) resueltos con `ADR-0003`/`ADR-0004` y la actualización del Constitution Check de
  `plan.md` — ver esos ficheros.
- **2026-08-25 (`spec-critic`, 2ª pasada, veredicto "GO condicionado")**: verificados de forma
  independiente los 7 hallazgos anteriores (todos confirmados resueltos) y encontrados 4 hallazgos
  nuevos, ya resueltos:
  - **Hallazgo A (bloqueante, acotado a Fase 5)**: T033 tal como estaba especificado corría el riesgo
    de ser un test de fachada, al depender del fixture `db_session` de rollback compartido
    (savepoint sobre una única conexión), que no ejerce contención real entre "sesiones concurrentes".
    Resuelto: T004 añade el fixture `db_engine` (conexiones independientes, sin rollback automático,
    limpieza manual) específicamente para T033; ver `research.md` §5.
  - **Hallazgo B**: SC-002 estaba redactado en términos absolutos pese a que ADR-0004 ya documentaba
    una excepción aceptada (ruta de usuario bloqueado, intencionalmente rápida). Resuelto: SC-002
    en `spec.md` ahora refleja esa excepción explícitamente.
  - **Hallazgo C**: T027/T028 estaban ambos marcados `[P]` pese a compartir fichero
    (`test_login_flow.py`), contradiciendo la propia definición de `[P]` de este documento. Resuelto:
    quitado `[P]` de T028.
  - **Hallazgo D**: SC-001 no tenía ninguna tarea que lo verificara. Resuelto: T045 (UAT) ahora
    referencia explícitamente la verificación manual de SC-001.
- **2026-08-25 (`spec-critic`, 3ª pasada, veredicto NO-GO, resuelto)**: confirmó B, C, D resueltos;
  encontró que el Hallazgo A solo estaba parcialmente resuelto (faltaba mecanismo de sincronización
  determinista) y 4 hallazgos nuevos:
  - **Hallazgo E (bloqueante)**: contradicción interna en `spec.md` — US3 y `quickstart.md` describían
    un mensaje de "bloqueo temporal" distinto del mensaje genérico único exigido por FR-006/SC-002.
    Resuelto: reescrito el "Independent Test" de US3 en `spec.md` y el escenario 3 de `quickstart.md`
    para exigir explícitamente el mismo mensaje genérico, distinguible solo por tiempo (SC-002).
  - **Hallazgo A (completado)**: el mecanismo "casi simultáneamente" no garantizaba solape real entre
    hilos (riesgo de test flaky). Resuelto: T033 reescrito con el patrón "bloqueo observado
    directamente" (conexión A retiene el lock deliberadamente, se verifica que B se bloquea), y
    verificación explícita, paso a paso, de que el mismo test falla sin `SELECT ... FOR UPDATE`. Ver
    `research.md` §5.
  - **Hallazgo F**: ninguna tarea creaba la BD de test ni aplicaba migraciones antes de la suite.
    Resuelto: T004 añade una fixture de sesión `autouse=True` que migra `TEST_DATABASE_URL`
    automáticamente al inicio de la suite (vía API programática de Alembic).
  - **Hallazgo G**: `session_token` en claro en `user_sessions`, riesgo no documentado como decisión
    consciente. Resuelto: `ADR-0005` documenta la aceptación explícita del riesgo (decisión del
    humano, sin cambio de esquema).
  - **Hallazgo H**: sin definir dónde vive la lista de proxies de confianza para
    `ProxyHeadersMiddleware`. Resuelto: variable de entorno `TRUSTED_PROXY_IPS` en `.env` (T015,
    `plan.md`).
- **2026-08-25 (`spec-critic`, 4ª pasada, veredicto NO-GO, resuelto)**: confirmó E, F(bootstrap) y G
  resueltos; encontró que A seguía sin resolverse del todo (el diseño "bloqueo observado
  directamente" tenía huecos técnicos de fondo) y 2 hallazgos menores nuevos:
  - **Hallazgo A (completado)**: T033 reescrito con: señal `lock_acquired` separada de `release_a`
    (garantiza que B nunca arranca antes de que A tenga el lock a nivel de BD, no solo por orden de
    líneas de Python); aserción determinista vía variable compartida `a_committed` en vez de medir
    reloj real (coherente con el criterio anti-flakiness ya aplicado en T027); `try/finally` para
    limpieza garantizada; y la variante negativa del paso 5 aclarada para que solo quite `FOR UPDATE`
    manteniendo el patrón leer-incrementar-escribir (sin el cual el contraste no demostraría nada,
    porque un `UPDATE` atómico de una sola sentencia ya serializa en Postgres independientemente de
    `FOR UPDATE`). T034 ahora especifica explícitamente ese patrón leer-incrementar-escribir.
  - **Hallazgo nuevo #5**: sin garantía de que la fixture de test (T004) migrase `TEST_DATABASE_URL`
    en vez de `DATABASE_URL`. Resuelto: T003 especifica que `env.py` lee la URL vía
    `config.get_main_option("sqlalchemy.url")`, y T004 la sobrescribe explícitamente antes de invocar
    Alembic.
  - **Hallazgo nuevo #6**: `CLAUDE.md` no documentaba `TEST_DATABASE_URL` ni `TRUSTED_PROXY_IPS`.
    Resuelto: añadidas ambas a la sección "Comandos" de `CLAUDE.md`.
- **2026-08-25 (implementación, `/speckit-implement`)**: T001-T044 implementadas con TDD (test en
  rojo antes de implementación en toda la lógica de seguridad). Durante la implementación se
  detectaron y corrigieron 2 problemas reales no vistos por ninguna de las 4 pasadas de
  `spec-critic`: (1) el diseño de T033 basado en `a_committed` no distinguía el caso correcto del
  incorrecto (en PostgreSQL, `UPDATE` bloquea por lock de fila independientemente de `FOR UPDATE`)
  — corregido con interlineado manual determinista para el control negativo, ver notas de T033
  arriba y `research.md` §5; (2) un `"version"` duplicado en el seed de `keys_catalog` de la
  migración (sin impacto funcional, detectado por `ruff check` F601). 43/43 tests en verde,
  `ruff check`/`ruff format --check`/`ty check` limpios.
- **2026-08-25 (T045, UAT humana confirmada)**: usuario ejecutó los 5 escenarios de `quickstart.md`.
  4/5 correctos sin observaciones. El punto 4 (sesión única) generó una pregunta: al hacer login en
  una segunda pestaña, la primera queda invalidada y cualquier acción en ella redirige a login como
  si nunca hubiera tenido sesión — confirmado como comportamiento correcto (FR-004, invalidación
  silenciosa ya decidida en la 3ª pasada de `spec-critic`), no un bug.
  Además, el usuario propuso mover `login_audit_log.result` a una FK compuesta contra un nuevo
  grupo de `keys_catalog` (como `permission_level`), buscando ahorrar espacio frente al
  `VARCHAR(20)` + `CHECK` actual. Evaluado y **descartado, con acuerdo del usuario**: a diferencia
  de `permission_level`, el dominio de `result` no puede crecer sin desplegar código nuevo (cada
  valor está atado 1:1 a una rama de `routers/login.py`/`lockout.py`), el ahorro de espacio real es
  marginal (Postgres almacena `VARCHAR` sin padding), y una FK compuesta añadiría coste de
  integridad referencial y un JOIN obligatorio para leer el log en una tabla pensada para escritura
  barata y lectura de auditoría simple (BRIN, append-only, purga a 90 días). `result` se mantiene
  como `VARCHAR(20)` + `CHECK`, sin cambios de esquema.
  **T045 cerrada.** Feature `001-login-skeleton` completa (45/45 tareas).
