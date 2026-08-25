# Implementation Plan: Esqueleto de login y modelo de datos base

**Branch**: `001-login-skeleton` | **Date**: 2026-08-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-login-skeleton/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Esqueleto E2E verificable de FastAPI + Jinja2 + PostgreSQL: login real (username o email + password
con hash Argon2id), sesión de servidor única por usuario, bloqueo temporal anti-fuerza-bruta (5
intentos → 15 min, con reseteo automático del contador), y auditoría de cada intento de login con
retención de 90 días. El modelo de datos (`keys_catalog`, `households`, `users`, `user_sessions`,
`login_audit_log`) ya fue diseñado y aprobado por `db-designer` y persistido en
`.specify/memory/data-model.md`. Sin registro de usuarios, recuperación de contraseña, gestión de
hogares ni 2FA — explícitamente fuera de alcance (ver `spec.md` → Assumptions).

## Technical Context

**Language/Version**: Python 3.14 (fijado por `constitution.md` Principio I y `.python-version`;
`pyproject.toml` ya declara `requires-python = ">=3.14"`).

**Primary Dependencies**: FastAPI + Jinja2 + uvicorn (ya en `pyproject.toml`). A añadir en esta
feature: SQLAlchemy 2.0 (ORM tipado, ya usado implícitamente por la convención de Alembic de
`CLAUDE.md`), `psycopg[binary]` (driver PostgreSQL v3, síncrono), Alembic (migraciones, ya fijado en
`CLAUDE.md`), `argon2-cffi` (hashing de contraseña, ver `research.md`). Pydantic v2 llega transitivo
vía FastAPI.

**Storage**: PostgreSQL (servicio local `postgresql-x64-18` según `CLAUDE.md`). Esquema ya aprobado
en `.specify/memory/data-model.md` (entidades introducidas en `001`).

**Testing**: `pytest` + `starlette.testclient.TestClient` (incluido con FastAPI) contra una base de
datos PostgreSQL de test real (mismo motor que producción — evita divergencias de comportamiento en
índices funcionales `LOWER(...)`, `CHECK`, FKs compuestas y BRIN que un motor distinto no replicaría),
apuntada por `TEST_DATABASE_URL` en `.env` (separada de `DATABASE_URL`), migrada automáticamente al
inicio de la suite (`tasks.md` → T004, ver `research.md` §5).

**Variables de entorno adicionales** (además de `DATABASE_URL`, ya documentada en `CLAUDE.md`):
`TEST_DATABASE_URL` (BD de test, ver arriba) y `TRUSTED_PROXY_IPS` (orígenes de confianza para
`ProxyHeadersMiddleware` — `tasks.md` → T015, `ADR-0003`).

**Target Platform**: Servidor Linux para despliegue (según `05_github.md`/CI); desarrollo local en
Windows sobre el mismo `pyproject.toml`/`uv.lock`.

**Project Type**: Web-service con SSR (FastAPI + Jinja2 en un único proyecto — Principio I de la
constitución ya descarta frontend/backend separados).

**Performance Goals**: SC-001 — login completo y página de bienvenida visible en <3s en condiciones
normales.

**Constraints**: bloqueo de login 15 min tras 5 intentos fallidos con reseteo automático (FR-007);
sesión única por usuario, cookie `HttpOnly`+`Secure` (FR-004, Assumptions); retención de auditoría de
login 90 días (FR-012); sin throttling por IP (fuera de alcance, ver Clarifications).

**Scale/Scope**: bajo volumen — uso doméstico/familiar, decenas de usuarios, sin concurrencia
significativa (spec → Assumptions). Sin requisitos de escalado horizontal.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación |
|---|---|
| I. Stack Tecnológico Fijo | ✅ Cumple — Python 3.14 + uv, src layout, FastAPI, FastAPI+Jinja2 (sin HTMX todavía porque esta feature no tiene interacciones parciales que lo requieran — page reloads simples de login/logout son suficientes; no es una desviación del stack, HTMX se usará cuando una feature lo necesite), PostgreSQL, Ruff/ty/pytest ya en `pyproject.toml`, Pydantic v2 transitivo. |
| II. Desarrollo Guiado por Spec-Kit | ✅ Cumple — dos pasadas de `/speckit.clarify` ya completadas antes de este plan; `spec-critic` pendiente antes de `/speckit.implement` (siguiente gate, no de este comando). |
| III. Test-First Estricto | ✅ Cumple (actualizado 2026-08-25 tras `spec-critic`) — el contador de bloqueo (FR-007), la verificación de credenciales (FR-003/FR-006) **y el registro de auditoría (FR-012)** son lógica de seguridad de negocio → exigen TDD estricto Red→Green→Refactor. `tasks.md` (T017/T018 auditoría, T019/T021 hashing+mitigación de timing, T031/T033/T034 lockout+concurrencia) refleja el test antes que la implementación en los tres casos. |
| IV. Documentación y Trazabilidad | ✅ Cumple (actualizado 2026-08-25) — la estrategia de autenticación/autorización queda documentada en `ADR-0002` (hashing Argon2id, sesión de servidor única, política de lockout), `ADR-0003` (detección de HTTPS/cookie `Secure` detrás de proxy inverso), `ADR-0004` (mitigación de enumeración de usuarios por timing en `POST /login`) y `ADR-0005` (aceptación consciente del riesgo de `session_token` en claro) — los cuatro `Aceptado`. Gate cerrado. |
| V. Integridad y Seguridad de Datos | ✅ Cumple — campos de auditoría completos en tablas transaccionales, desviaciones (`user_sessions`, `login_audit_log`) justificadas explícitamente por `db-designer` en `data-model.md`. Sin migración sobre datos de producción existentes (proyecto sin datos previos). `.env`/`DATABASE_URL` no se tocan en este plan. |

No hay violaciones que requieran `Complexity Tracking` — la tabla se deja vacía.

**Re-check post Phase 1**: tras generar `data-model.md`, `contracts/login.md` y `quickstart.md`, la
evaluación no cambia — ningún artefacto de diseño introduce una violación nueva.

**Re-check post `spec-critic` (2026-08-25)**: el subagente `spec-critic` devolvió NO-GO sobre la
primera versión de `tasks.md` por 3 hallazgos bloqueantes (Polish sin tests, riesgo de enumeración
por timing en login, orden TDD de la auditoría invertido) y 4 no bloqueantes (ADR desactualizado,
este propio Constitution Check desincronizado, lockout sin test de concurrencia, detección de HTTPS
sin contemplar proxy inverso). Todos resueltos: `tasks.md` reescrito (T001–T045), `ADR-0003` y
`ADR-0004` creados, y las filas III/IV de este Constitution Check actualizadas arriba.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/financial_health_app/
├── __init__.py
├── main.py                    # FastAPI app factory + montaje de routers/templates
├── db.py                      # engine SQLAlchemy, sessionmaker, dependency get_db()
├── models/
│   ├── __init__.py
│   ├── household.py
│   ├── user.py
│   ├── user_session.py
│   ├── login_audit_log.py
│   └── keys_catalog.py
├── auth/
│   ├── __init__.py
│   ├── hashing.py              # argon2-cffi: hash_password / verify_password
│   ├── session.py              # crear/validar/invalidar sesión (user_sessions)
│   ├── lockout.py              # contador de intentos fallidos + locked_until (FR-007)
│   └── audit.py                # record_login_attempt(): escribe en login_audit_log (FR-012)
├── routers/
│   ├── __init__.py
│   └── login.py                # GET/POST /login, POST /logout, GET / (bienvenida)
└── templates/
    ├── base.html
    ├── login.html
    └── welcome.html

alembic/
├── env.py
└── versions/                   # primera migración: crea keys_catalog, households, users,
                                 # user_sessions, login_audit_log + seed NUS (ver data-model.md)
alembic.ini

scripts/
├── seed_user.py                 # hashea con argon2-cffi e inserta el usuario semilla (UAT)
└── purge_login_audit_log.py     # borra filas de login_audit_log con más de 90 días (FR-012)

tests/
├── unit/
│   ├── test_hashing.py
│   └── test_lockout.py
├── integration/
│   └── test_login_flow.py      # US1/US2/US3 contra la BD de test real
└── conftest.py                 # fixture de sesión de BD de test (rollback por test)
```

**Structure Decision**: Proyecto único (Opción 1 del template), coherente con el Principio I de la
constitución (FastAPI + Jinja2 SSR en un solo proyecto, sin frontend/backend separados). Se extiende
el `src/financial_health_app/` ya existente con los subpaquetes `models/`, `auth/`, `routers/` y
`templates/`; no se crea ningún proyecto ni paquete adicional. `alembic/` vive en la raíz del repo
(convención estándar de Alembic, fuera de `src/`, para no mezclar código de migración con el paquete
distribuible).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Sin violaciones — tabla vacía.
