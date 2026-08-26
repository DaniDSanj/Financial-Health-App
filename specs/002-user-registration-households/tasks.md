# Tasks: Registro de usuarios y gestión de hogares

**Input**: Design documents from `specs/002-user-registration-households/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/register.md,
contracts/household.md, quickstart.md

**Tests**: Obligatorios per constitución Principio III (Test-First Estricto). Lógica de negocio de
seguridad (validación de registro, código de invitación, bloqueo, auditoría, condiciones de carrera)
exige TDD estricto: test escrito y en rojo antes de la implementación. El resto de tareas exige al
menos un test antes de cerrarse, sin requerir orden TDD estricto.

**Organization**: Tareas agrupadas por user story (US1/US2/US3, prioridad P1/P2/P3 de `spec.md`) para
permitir implementación y verificación independientes de cada una.

**Nota de renumeración (2026-08-26)**: esta versión incorpora 2 tareas nuevas y 3 tareas de
implementación extendidas, resultado de la revisión adversarial de `spec-critic` (gate obligatorio
antes de `/speckit.implement`, Principio II) — ver `checklists/requirements.md` → Notes para el
detalle completo de los hallazgos y las decisiones del humano. `tasks.md` no se había convertido
todavía a Issues de GitHub, por lo que la renumeración completa desde T006 en adelante es segura (sin
Issues huérfanos que reconciliar).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (ficheros distintos, sin dependencias pendientes)
- **[Story]**: A qué user story pertenece (US1, US2, US3) — solo en fases 3-5
- Cada tarea incluye la ruta exacta del fichero a crear/modificar

## Path Conventions

Proyecto único (ver `plan.md` → Project Structure), extendiendo el ya existente desde
`001-login-skeleton`: `src/financial_health_app/`, `alembic/`, `tests/`, `scripts/` en la raíz del
repo.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prerrequisito mínimo antes de poder correr los tests de esta feature. Sin dependencias
nuevas que instalar (`research.md` §2: el hash HMAC-SHA256 usa `hmac`/`hashlib` de la librería
estándar).

- [X] T001 [P] Añadir `INVITE_CODE_HMAC_SECRET` al `.env` local (generar con
  `python -c "import secrets; print(secrets.token_hex(32))"`, ver ADR-0006) — prerrequisito para
  cualquier test que ejercite `auth/invite_code.py` (Fase 5).

**Checkpoint**: Entorno local listo para correr tests de esta feature.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestructura común que TODAS las user stories necesitarían antes de empezar.

**Sin tareas nuevas en esta fase.** A diferencia de `001-login-skeleton` (que creaba toda la
infraestructura de autenticación desde cero), esta feature reutiliza íntegramente
`auth/hashing.py`/`auth/session.py` ya existentes y no introduce ninguna pieza compartida por las 3
historias a la vez:
- US1 (registro) solo usa piezas ya existentes de `001`.
- US2 (crear hogar) solo toca `households`, sin cambio de esquema.
- US3 (unirse por código) es la única que introduce esquema/módulos nuevos — viven dentro de su
  propia fase (Fase 5), no aquí, per la regla de generación de tareas ("si una entidad sirve a una
  sola historia, va en esa historia, no en Foundational").

**Checkpoint**: N/A — pasar directamente a la Fase 3.

---

## Phase 3: User Story 1 - Alta de un nuevo usuario (Priority: P1) 🎯 MVP

**Goal**: Un visitante sin cuenta se registra (nombre, apellidos, username, email, contraseña) y
queda autenticado de inmediato, sin hogar asociado todavía.

**Independent Test**: Acceder a `/register` sin ningún usuario ni invitación previa, completar el
formulario con datos válidos no usados antes, y comprobar que la cuenta queda creada y el usuario
autenticado de inmediato (quickstart.md, escenario 1).

### Tests for User Story 1 (obligatorio per constitución Principio III) ⚠️

> **NOTA: escribir estos tests PRIMERO, comprobar que fallan antes de implementar**

- [X] T002 [P] [US1] Test de integración del registro completo: Acceptance Scenarios 1–3 de US1
  (alta + auto-login, username/email duplicado con distinta capitalización rechazado FR-002,
  contraseña fuera de rango rechazada), más FR-009 (login inmediato sin paso adicional), FR-011
  (longitudes mínima/máxima de contraseña 8/128, máximas de username/email/first_name/last_name
  50/255/100/50, y rechazo de caracteres no-ASCII en username/email), y FR-012 (la fila creada en
  `users` lleva `created_at` — auditoría de alta) en `tests/integration/test_register_flow.py`.
- [X] T003 [P] [US1] Test de integración de concurrencia de registro: dos peticiones
  `POST /register` simultáneas con el mismo `username` o `email` (incluida distinta capitalización),
  usando el fixture `db_engine` (no `db_session`, que no ejerce contención real — mismo criterio que
  `research.md` §7); verificar que exactamente una tiene éxito (`303`) y la otra recibe `409` (nunca
  `500`) gracias a la captura de `IntegrityError` de T005, en
  `tests/integration/test_register_concurrency.py`.

### Implementation for User Story 1

- [X] T004 [P] [US1] `src/financial_health_app/templates/register.html`: formulario con campos
  `first_name`, `last_name` (opcional), `username`, `email`, `password` (extiende `base.html`).
- [X] T005 [US1] `src/financial_health_app/routers/register.py`: `GET /register`, `POST /register`
  per `contracts/register.md` — valida campos, longitudes (FR-011) y charset ASCII de
  `username`/`email` (FR-011), comprueba unicidad de username/email insensible a mayúsculas (FR-002,
  `409` si ya existe), hashea la contraseña reutilizando `auth/hashing.hash_password` (FR-003),
  inserta en `users` (`household_id=NULL`, `permission_level_group='NUS'`,
  `permission_level_code='MEM'` por defecto) **capturando `IntegrityError` en el `INSERT` y
  traduciéndola a `409`** (cierra la ventana de carrera que T003 ejercita), crea sesión reutilizando
  `auth/session.create_session` (auto-login, FR-009, `research.md` §3), fija cookie de sesión
  (mismos atributos que `POST /login` de 001). Depende de T002, T003, T004.
- [X] T006 [US1] Montar el router de registro en `src/financial_health_app/main.py`. Depende de T005.

**Checkpoint**: User Story 1 funcional y verificable de forma independiente.

---

## Phase 4: User Story 2 - Creación de un hogar nuevo (Priority: P2)

**Goal**: Un usuario autenticado sin hogar crea uno nuevo (nombre, hasta 100 caracteres) y queda
asociado como administrador (`ADM`).

**Independent Test**: Con un usuario autenticado sin hogar (vía T005 o insertado directamente),
crear un hogar nuevo desde `/household` y comprobar que queda asociado como `ADM` (quickstart.md,
escenario 2).

### Tests for User Story 2 (obligatorio per constitución Principio III) ⚠️

- [X] T007 [P] [US2] Test de integración de creación de hogar: Acceptance Scenarios de US2 (crear
  hogar → `ADM`; ya tiene hogar → rechazado FR-008), FR-005 (nombre vacío, solo espacios, o >100
  caracteres rechazado; **y caso positivo**: dos hogares creados con el mismo nombre tienen éxito
  ambos, FR-014), y FR-012 (la fila creada en `households` lleva `created_by`) en
  `tests/integration/test_household_flow.py`.
- [X] T008 [P] [US2] Test de integración de concurrencia de creación de hogar: dos peticiones
  `POST /household/create` simultáneas del mismo usuario, usando el fixture `db_engine`; verificar
  que exactamente una tiene éxito (`303`, con `permission_level_code='ADM'`) y la otra recibe `409`
  (mediante la `UPDATE` condicional de T011), y que no queda ningún hogar sin ningún usuario
  apuntándolo vía `household_id` (FR-008), en
  `tests/integration/test_household_create_concurrency.py`.

### Implementation for User Story 2

- [X] T009 [P] [US2] `src/financial_health_app/templates/household.html`: vista "sin hogar" (dos
  formularios — crear hogar `name`, y unirse por código `code`, este último con su acción ya
  apuntando a `POST /household/join` aunque la ruta la implemente la Fase 5) y vista "con hogar"
  (nombre, nivel de permisos, botón para generar código de invitación) per `contracts/household.md`.
- [X] T010 [US2] `src/financial_health_app/templates/welcome.html`: añadir bloque de estado de
  hogar — nombre del hogar si el usuario tiene uno, enlace a `/household` si no (SC-005).
- [X] T011 [US2] `src/financial_health_app/routers/household.py`: `GET /household` (renderiza la
  vista según tenga o no `household_id`) y `POST /household/create` per `contracts/household.md`
  (valida nombre no vacío/no solo espacios/≤100, rechaza si ya tiene hogar con `409`, inserta
  `households` con `created_by`, y actualiza `users` de forma **atómica y condicional**:
  `UPDATE users SET household_id=:id, permission_level_code='ADM' WHERE id=:user_id AND
  household_id IS NULL` — si afecta 0 filas, `ROLLBACK` de toda la transacción incluido el `INSERT`
  de `households` y `409`, cerrando la condición de carrera que T008 ejercita). Depende de T007,
  T008, T009, T010.
- [X] T012 [US2] Montar el router de hogar en `src/financial_health_app/main.py`. Depende de T011.

**Checkpoint**: User Stories 1 y 2 funcionan de forma independiente.

---

## Phase 5: User Story 3 - Asociación a un hogar existente mediante código de invitación (Priority: P3)

**Goal**: Un usuario autenticado sin hogar introduce un código de invitación de 8 caracteres
generado por un miembro de un hogar existente y queda asociado como miembro (`MEM`); protegido por
bloqueo tras 5 intentos fallidos (FR-013) y con auditoría de cada intento (FR-015).

**Independent Test**: Con un hogar ya existente (vía T011) y un código generado por uno de sus
miembros, un segundo usuario autenticado sin hogar introduce ese código y queda asociado
(quickstart.md, escenario 3).

### Tests for User Story 3 (obligatorio per constitución Principio III) ⚠️

- [X] T013 [P] [US3] Test unitario de `auth/invite_code.py`: `generate_code()` produce 8 caracteres
  del alfabeto sin ambiguos (`research.md` §1); `hash_code()`/`verify_code()` (HMAC-SHA256,
  determinista, `hmac.compare_digest`) en `tests/unit/test_invite_code.py`.
- [X] T014 [P] [US3] Test unitario de `auth/invite_lockout.py`: 5 fallos consecutivos activan
  bloqueo de 15 min, 6º intento rechazado, reseteo automático del contador al expirar sin intento
  correcto previo (FR-013) en `tests/unit/test_invite_lockout.py`.
- [X] T015 [US3] Test de integración del flujo completo de US3: Acceptance Scenarios 1–4 (join
  correcto → `MEM` + código invalidado; código usado/caducado/inexistente rechazado; usuario con
  hogar rechazado; bloqueo tras 5 fallos), más FR-007 (el código se devuelve una única vez y no es
  recuperable en una segunda petición) y FR-015 (fila en `household_invitation_attempts_log` por
  cada intento, con `result` correcto: `success`/`failure`/`locked`, **y `household_id` poblado
  correctamente al fallar con un código que sí corresponde a una invitación real ya usada/caducada,
  distinto de `household_id=NULL` cuando el código no existe en absoluto** — ver búsqueda secundaria
  de auditoría en T026) en `tests/integration/test_household_flow.py` — **sin** `[P]`: comparte
  fichero con T007 (mismo criterio que Hallazgo C de `001-login-skeleton`).
- [X] T016 [P] [US3] Test de integración de la migración: `alembic upgrade head` crea
  `household_invitations` y `household_invitation_attempts_log`, y añade `failed_invite_attempts`/
  `invite_locked_until` a `users`, en `tests/integration/test_migration_invitations.py` (test
  mínimo obligatorio para una tarea no de lógica de negocio, per constitución Principio III).
- [X] T017 [P] [US3] Test de integración de concurrencia: dos conexiones intentan consumir el mismo
  código válido simultáneamente (`UPDATE ... WHERE used_at IS NULL`); se verifica que exactamente
  una tiene éxito y la otra recibe el mismo resultado que un código ya usado (FR-006) en
  `tests/integration/test_invite_code_concurrency.py`, usando el fixture `db_engine` (no
  `db_session`, que no ejerce contención real — mismo criterio que `research.md` §7).
- [X] T018 [P] [US3] Test de integración de concurrencia del contador de bloqueo (mismo patrón
  "bloqueo observado directamente" que `tests/integration/test_lockout_concurrency.py` de `001`:
  conexión A retiene el lock vía `SELECT ... FOR UPDATE`, señal `lock_acquired` antes de lanzar B,
  verificación del contador final tras ambas escrituras; control negativo sin `FOR UPDATE` con
  interlineado manual sin hilos) en `tests/integration/test_invite_lockout_concurrency.py`.

### Implementation for User Story 3

- [X] T019 [P] [US3] Modelo `HouseholdInvitation` en
  `src/financial_health_app/models/household_invitation.py` — columnas y constraints exactos de
  `data-model.md` → `household_invitations` (incluye `CHECK ((used_at IS NULL) = (used_by IS
  NULL))`, índices `household_id`/`created_by`/`used_by`/`code_hash`).
- [X] T020 [P] [US3] Modelo `HouseholdInvitationAttemptLog` en
  `src/financial_health_app/models/household_invitation_attempt_log.py` — per `data-model.md` →
  `household_invitation_attempts_log` (`result` CHECK IN success/failure/locked, índice BRIN sobre
  `occurred_at`).
- [X] T021 [P] [US3] Extender el modelo `User` en `src/financial_health_app/models/user.py`:
  añadir `failed_invite_attempts` (`INTEGER NOT NULL DEFAULT 0`) e `invite_locked_until`
  (`TIMESTAMPTZ NULL`).
- [X] T022 [US3] Migración Alembic en `alembic/versions/` que crea `household_invitations` →
  `household_invitation_attempts_log` → `ALTER TABLE users` en ese orden (`data-model.md` → "Orden
  de creación"). Depende de T019, T020, T021. **Nota: esta migración es aditiva pero toca `users`,
  tabla con datos reales — requiere UAT humana explícita antes de aplicarse fuera de un entorno de
  test** (misma regla que cualquier migración sobre datos existentes, `01_estilo_comportamiento.md`
  §3).
- [X] T023 [P] [US3] `src/financial_health_app/auth/invite_code.py`: `generate_code()` (8
  caracteres, alfabeto sin `0`/`O`/`1`/`I`/`l`, vía `secrets.choice`) y `hash_code()`/`verify_code()`
  (HMAC-SHA256 con `INVITE_CODE_HMAC_SECRET`, ADR-0006). Depende de T013.
- [X] T024 [P] [US3] `src/financial_health_app/auth/invite_lockout.py`: `check_lockout(user)`,
  `register_failed_attempt(db, user)`, `reset_lockout(user)` sobre
  `failed_invite_attempts`/`invite_locked_until` — mismo patrón `SELECT ... FOR UPDATE`
  leer-incrementar-escribir que `auth/lockout.py` de `001`. Depende de T014, T021.
- [X] T025 [P] [US3] `src/financial_health_app/auth/invite_audit.py`:
  `record_invite_attempt(db, *, user_id, household_id, result)` que escribe una fila en
  `household_invitation_attempts_log` (FR-015). Depende de T020.
- [X] T026 [US3] Extender `src/financial_health_app/routers/household.py`:
  `POST /household/join` (comprueba bloqueo → calcula hash → busca invitación vigente → si no hay,
  **realiza además una búsqueda secundaria por `code_hash` sin los filtros `used_at IS NULL`/
  `expires_at > now()`, solo para identificar `household_id` en el log de auditoría cuando el código
  sí corresponde a una invitación real ya usada/caducada** (FR-015; `NULL` solo si el código no
  corresponde a ninguna invitación existente en absoluto) → registra fallo/incrementa
  contador/audita; si hay invitación vigente, consume atómicamente
  `UPDATE household_invitations SET used_at=now(), used_by=:user_id WHERE id=:id AND used_at IS
  NULL`, actualiza `users.household_id`/`permission_level_code='MEM'`, resetea contador, audita
  éxito) y `POST /household/invite` (genera código, inserta `household_invitations` con
  `expires_at = now() + 24h`, muestra el código en claro una única vez) per
  `contracts/household.md`. Depende de T015, T011, T019, T022, T023, T024, T025.

**Checkpoint**: Las 3 user stories son funcionales e independientemente verificables.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mejoras transversales. Cada tarea de implementación lleva su test asociado ANTES en la
numeración (Principio III: ninguna tarea se cierra sin al menos un test, sin excepción por ser fase
de Polish).

### Tests for Polish (obligatorio per constitución Principio III) ⚠️

- [X] T027 [P] Test: `register.html` renderiza `autocomplete="off"` en el campo password, en
  `tests/integration/test_templates.py` (mismo fichero que el test de `login.html` de `001`).
- [X] T028 [P] Test: `scripts/purge_household_invitation_attempts_log.py` borra únicamente las
  filas de `household_invitation_attempts_log` con `occurred_at` de más de 90 días, retiene las de
  90 días o menos, y trata correctamente el caso límite exacto de 90 días, en
  `tests/integration/test_purge_invite_attempts_script.py`.

### Implementation for Polish

- [X] T029 [P] Añadir `autocomplete="off"` al campo password en `register.html`. Depende de T027.
- [X] T030 [P] `scripts/purge_household_invitation_attempts_log.py`: borra filas de
  `household_invitation_attempts_log` con más de 90 días de antigüedad (FR-015), mismo patrón que
  `scripts/purge_login_audit_log.py` de `001`. Depende de T028.
- [X] T031 `uv run ruff check --fix src/` + `uv run ruff format src/` + `uv run ty check` sobre todo
  `src/` y `tests/`.
- [X] T032 Ejecutar el guion UAT completo de `quickstart.md` (5 escenarios). **No marcar esta tarea
  como Done sin confirmación humana explícita** — flujo user-facing, UAT obligatoria per
  `01_estilo_comportamiento.md` §3.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias — puede empezar de inmediato.
- **Foundational (Phase 2)**: sin tareas — no bloquea nada.
- **User Stories (Phase 3+)**: no dependen de Foundational (vacía). US1 no depende de otras
  historias. US2 no depende de US1 a nivel de código (solo necesita un usuario autenticado, que
  puede venir de T005 o de un seed directo) pero comparte `main.py` (montaje de routers). US3
  extiende el mismo `routers/household.py`/`templates/household.html` que crea US2 — requiere US2
  implementada primero a nivel de código, pero es verificable de forma independiente por sus propios
  Acceptance Scenarios (con un hogar ya existente, da igual cómo se creó).
- **Polish (Final Phase)**: depende de que las user stories deseadas estén completas.

### Within Each User Story / Fase

- Tests (obligatorios) se escriben y deben fallar ANTES de la implementación — incluida la fase de
  Polish (T027/T028 antes de T029/T030).
- Modelos (T019–T021) antes que la migración (T022) antes que los módulos `auth/invite_*` que los
  usan (T023–T025) antes del router (T026).
- Implementación core antes que integración entre historias.

### Parallel Opportunities

- T002, T003 (tests US1) en paralelo entre sí; T004 (template) en paralelo con ambos; T005 depende
  de los tres.
- T007, T008 (tests US2) en paralelo entre sí; T009, T010 (templates) en paralelo con ambos; T011
  depende de los cuatro.
- T013, T014 (tests unitarios US3) en paralelo entre sí y con T016/T017/T018 (distintos ficheros).
  T015 NO es paralelo a T007 (comparten `test_household_flow.py`).
- T019, T020, T021 (modelos US3) en paralelo.
- T023, T024, T025 (módulos `auth/invite_*`) en paralelo entre sí (ficheros distintos), aunque cada
  uno depende de su propio test/modelo previo.
- T027, T028 (tests Polish) en paralelo; T029, T030 (implementación Polish) en paralelo.

---

## Parallel Example: User Story 3

```bash
# Tests de US3 en paralelo:
Task: "Test unitario auth/invite_code.py en tests/unit/test_invite_code.py"
Task: "Test unitario auth/invite_lockout.py en tests/unit/test_invite_lockout.py"
Task: "Test de migración en tests/integration/test_migration_invitations.py"
Task: "Test de concurrencia de consumo de código en tests/integration/test_invite_code_concurrency.py"
Task: "Test de concurrencia de bloqueo en tests/integration/test_invite_lockout_concurrency.py"

# Modelos de US3 en paralelo:
Task: "Modelo HouseholdInvitation en models/household_invitation.py"
Task: "Modelo HouseholdInvitationAttemptLog en models/household_invitation_attempt_log.py"
Task: "Extender modelo User en models/user.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 solamente)

1. Completar Phase 1: Setup.
2. Completar Phase 3: User Story 1 (Foundational no tiene tareas).
3. **PARAR y VALIDAR**: probar el registro de forma independiente.
4. Demo si está listo.

### Incremental Delivery

1. Setup → base lista (Foundational vacía).
2. + User Story 1 → validar de forma independiente → MVP.
3. + User Story 2 → validar de forma independiente.
4. + User Story 3 → validar de forma independiente.
5. + Polish → UAT completa (T032) antes de `/speckit.converge`.

---

## Notes

- [P] = ficheros distintos, sin dependencias entre sí.
- [Story] mapea la tarea a su user story para trazabilidad.
- Verificar que los tests fallan antes de implementar (TDD, Principio III de la constitución) —
  incluida la fase de Polish, sin excepción.
- No se cierra T022 (migración) sin UAT humana antes de aplicarse fuera de un entorno de test; no se
  cierra T032 (UAT final) sin confirmación humana explícita.
- Los 25 items de `checklists/general.md` (resueltos el 2026-08-26) ya están reflejados en `spec.md`
  antes de generar estas tareas — no generan tareas adicionales por sí mismos, solo precisaron los
  FR/Assumptions que las tareas de arriba ya implementan.
- `/speckit.analyze` (2026-08-26) resolvió 5 hallazgos menores de consistencia entre spec/plan/tasks/
  contratos — ver `checklists/requirements.md` → Notes.
- El subagente `spec-critic` (2026-08-26) devolvió veredicto **GO condicionado** con 9 hallazgos no
  bloqueantes; los 4 que implicaban una decisión de diseño real (confirmados por el humano) motivaron
  las tareas nuevas T003/T008 y la extensión de T005/T011/T026 en esta versión — ver
  `checklists/requirements.md` → Notes para el detalle completo. Gate de `/speckit.implement` ya
  superado.
