# Implementation Plan: Registro de usuarios y gestión de hogares

**Branch**: `002-user-registration-households` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-user-registration-households/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Alta de usuario (self-registration, sustituye a `scripts/seed_user.py` como única vía), creación de
hogar y asociación a un hogar existente mediante código de invitación de un solo uso (8 caracteres
alfanuméricos, hasheado con HMAC-SHA256 — ADR-0006, caduca a las 24h). Bloqueo anti-fuerza-bruta de
15 minutos tras 5 intentos fallidos de código (mismo patrón que el lockout de login de
`001-login-skeleton`), con su propio log de auditoría (`household_invitation_attempts_log`,
retención 90 días, simétrico a `login_audit_log`). El modelo de datos (tablas nuevas
`household_invitations`/`household_invitation_attempts_log` + extensión de `users`) ya fue diseñado
y aprobado por `db-designer` y persistido en `.specify/memory/data-model.md`, tras evaluar
explícitamente el impacto sobre `001-login-skeleton` (protocolo de cambio de esquema, migración
puramente aditiva). Recuperación de contraseña y 2FA permanecen fuera de alcance (FR-010).

## Technical Context

**Language/Version**: Python 3.14 (fijado por `constitution.md` Principio I; `pyproject.toml`
declara `requires-python = ">=3.14"`, mismo entorno que `001-login-skeleton`).

**Primary Dependencies**: Ninguna dependencia nueva — reutiliza íntegramente lo ya instalado en
`pyproject.toml` desde `001`: FastAPI + Jinja2 + uvicorn, SQLAlchemy 2.0, `psycopg[binary]`, Alembic,
`argon2-cffi` (contraseñas, sin cambios). El hash HMAC-SHA256 del código de invitación (ADR-0006) se
implementa con los módulos `hmac`/`hashlib` de la librería estándar — no requiere ninguna librería
adicional.

**Storage**: PostgreSQL (mismo servicio local `postgresql-x64-18`). Esquema ampliado en esta feature:
tablas nuevas `household_invitations`, `household_invitation_attempts_log`; `users` extendida con
`failed_invite_attempts`/`invite_locked_until` (ver `.specify/memory/data-model.md` y
`data-model.md` local).

**Testing**: `pytest` + `starlette.testclient.TestClient` contra la misma base de datos PostgreSQL de
test real ya bootstrapeada por `tests/conftest.py` (fixture de sesión que migra `TEST_DATABASE_URL`
con Alembic) — sin cambios de infraestructura de test respecto a `001`.

**Variables de entorno adicionales** (además de `DATABASE_URL`/`TEST_DATABASE_URL`/
`TRUSTED_PROXY_IPS`, ya documentadas en `CLAUDE.md`): `INVITE_CODE_HMAC_SECRET` (secreto de
aplicación para el HMAC del código de invitación — ADR-0006, ya añadida a `CLAUDE.md`).

**Target Platform**: Igual que `001` — servidor Linux en despliegue (CI/`05_github.md`), desarrollo
local en Windows sobre el mismo `pyproject.toml`/`uv.lock`.

**Project Type**: Web-service con SSR (FastAPI + Jinja2), mismo proyecto único que `001` — sin
frontend/backend separados (Principio I).

**Performance Goals**: SC-001/SC-003/SC-004 — registro completo en <2 min, crear/asociarse a un
hogar en <1 min, en condiciones normales.

**Constraints**: bloqueo de introducción de código 15 min tras 5 intentos fallidos con reseteo
automático (FR-013); código de invitación de un solo uso, caduca a las 24h (FR-006); nombre de hogar
no único (FR-014); sin protección anti-abuso en el registro abierto ni throttling por IP en el
bloqueo de códigos (fuera de alcance, ver spec → Assumptions).

**Scale/Scope**: mismo volumen bajo ya asumido en `001` — uso doméstico/familiar, decenas de
usuarios, sin concurrencia significativa. Sin requisitos de escalado horizontal.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación |
|---|---|
| I. Stack Tecnológico Fijo | ✅ Cumple — mismo stack que 001, sin dependencias nuevas (HMAC vía stdlib). PostgreSQL sigue siendo el único motor; no se introduce Redis pese a que `db-designer` señaló que encajaría conceptualmente (ver `data-model.md` → Nota NoSQL), por consistencia con el patrón ya establecido y para no añadir infraestructura sin necesidad medida. |
| II. Desarrollo Guiado por Spec-Kit | ✅ Cumple — 2 pasadas de `/speckit.clarify` completadas antes de este plan; protocolo de cambio de esquema aplicado explícitamente (impacto sobre `users` presentado al humano y aprobado antes de tocar `data-model.md`); `spec-critic` pendiente antes de `/speckit.implement` (siguiente gate, no de este comando). |
| III. Test-First Estricto | ✅ Cumple — resuelto en `/speckit.tasks`: el bloqueo de códigos (FR-013), la validación HMAC del código (FR-006) y el registro de auditoría (FR-015) tienen TDD estricto Red→Green→Refactor (T011-T016 antes de T017-T024), mismo criterio que 001 aplicó a login/lockout/auditoría; el resto de tareas lleva al menos un test antes de cerrarse (T002, T006, T025, T026). |
| IV. Documentación y Trazabilidad | ✅ Cumple — estrategia de hash del código documentada en `ADR-0006` (Aceptado); sin necesidad de un ADR adicional para el resto de decisiones de esta feature (reutilizan patrones ya fijados por ADR-0002 de 001, no son decisiones nuevas). |
| V. Integridad y Seguridad de Datos | ✅ Cumple — campos de auditoría completos donde aplica, desviaciones (`household_invitations` sin `updated_at`/`updated_by`/`version`; `household_invitation_attempts_log` sin `created_by`/`updated_by`/`version`) justificadas explícitamente por `db-designer` en `data-model.md`. La única migración con impacto en datos ya existentes (`ALTER TABLE users`) queda marcada como pendiente de UAT humana explícita antes de aplicarse en cualquier entorno con datos reales — no se aplica en este plan. |

No hay violaciones que requieran `Complexity Tracking` — la tabla se deja vacía.

**Re-check post Phase 1**: tras generar `research.md`, `contracts/` y `quickstart.md`, la evaluación
no cambia — ningún artefacto de diseño introduce una violación nueva. El único punto abierto (III,
TDD reflejado en `tasks.md`) se resuelve en `/speckit.tasks`, no en este comando.

## Project Structure

### Documentation (this feature)

```text
specs/002-user-registration-households/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command) — ya escrito por db-designer
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/financial_health_app/
├── __init__.py
├── main.py                          # sin cambios de estructura; se añaden los 2 routers nuevos
├── db.py                            # sin cambios
├── models/
│   ├── household.py                 # sin cambios de esquema (households ya existía)
│   ├── user.py                      # + failed_invite_attempts, invite_locked_until
│   ├── household_invitation.py      # nuevo — tabla household_invitations
│   └── household_invitation_attempt_log.py   # nuevo — tabla household_invitation_attempts_log
├── auth/
│   ├── hashing.py                   # sin cambios (Argon2id, solo contraseñas — ADR-0006)
│   ├── session.py                   # sin cambios; reutilizado tal cual tras el registro (auto-login)
│   ├── lockout.py                   # sin cambios (bloqueo de login, 001)
│   ├── audit.py                     # sin cambios (login_audit_log, 001)
│   ├── invite_code.py               # nuevo — generar código (alfabeto sin ambiguos) + hash/verify HMAC-SHA256 (ADR-0006)
│   ├── invite_lockout.py            # nuevo — bloqueo por intentos de código (FR-013), mismo patrón que lockout.py
│   └── invite_audit.py              # nuevo — record_invite_attempt() -> household_invitation_attempts_log (FR-015)
├── routers/
│   ├── login.py                     # ligero cambio: welcome.html pasa a mostrar el hogar si existe
│   ├── register.py                  # nuevo — GET/POST /register
│   └── household.py                 # nuevo — GET /household, POST /household/create, POST /household/join, POST /household/invite
└── templates/
    ├── base.html                    # sin cambios
    ├── login.html                   # sin cambios
    ├── welcome.html                 # + bloque de estado de hogar (nombre o enlace a /household)
    ├── register.html                # nuevo
    └── household.html                # nuevo — dashboard de hogar (crear/unirse, o detalle + generar invitación)

alembic/
└── versions/                        # nueva migración: household_invitations, household_invitation_attempts_log,
                                      # ALTER TABLE users (ver data-model.md → Orden de creación)

scripts/
├── seed_user.py                     # sin cambios
├── purge_login_audit_log.py         # sin cambios
└── purge_household_invitation_attempts_log.py   # nuevo — purga >90 días (FR-015), mismo patrón que el de login

tests/
├── unit/
│   ├── test_invite_code.py          # generación + hash/verify HMAC-SHA256
│   └── test_invite_lockout.py       # contador + bloqueo de 15 min (FR-013)
├── integration/
│   ├── test_register_flow.py        # US1 (alta, duplicados, contraseña <8, auto-login)
│   ├── test_register_concurrency.py # US1 (carrera de unicidad username/email, IntegrityError→409)
│   ├── test_household_flow.py       # US2/US3 (crear, unirse por código, un hogar a la vez, código caducado/usado)
│   ├── test_household_create_concurrency.py # US2 (doble creación simultánea, UPDATE condicional→409)
│   └── test_invite_lockout_concurrency.py   # mismo patrón que test_lockout_concurrency.py de 001 (SELECT...FOR UPDATE)
└── conftest.py                      # sin cambios (fixtures ya cubren cualquier tabla nueva vía migración Alembic)
```

**Structure Decision**: Se extiende el proyecto único ya existente (`src/financial_health_app/`),
mismo patrón que `001-login-skeleton` — sin crear ningún paquete ni proyecto nuevo. Los módulos
nuevos siguen el mismo layout por responsabilidad (`models/`, `auth/`, `routers/`, `templates/`) ya
establecido, en vez de introducir una organización distinta para esta feature.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Sin violaciones — tabla vacía.
