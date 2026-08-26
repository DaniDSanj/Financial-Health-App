# Changelog

Todas las modificaciones notables de este proyecto se documentan en este fichero.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto se adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [0.2.0] - 2026-08-26

### Added

- Registro de usuarios abierto (self-registration) y gestión de hogares — feature
  `002-user-registration-households`:
  - Formulario `/register` (nombre, apellidos opcional, username, email, contraseña de 8 a 128
    caracteres sin composición forzada, alineado con NIST 800-63B), con unicidad case-insensitive
    de username/email (FR-002) y auto-login inmediato tras el alta, sin verificación de email
    (FR-009). Sustituye a `scripts/seed_user.py` como vía real de alta.
  - Creación de hogar (`POST /household/create`): el creador queda asociado como administrador
    (`ADM`); un usuario pertenece como máximo a un hogar a la vez, con protección atómica frente a
    condiciones de carrera en creación simultánea (FR-008).
  - Asociación a un hogar existente mediante código de invitación alfanumérico de 8 caracteres
    (`POST /household/join`), generado por cualquier miembro (`POST /household/invite`), mostrado
    en claro una única vez, de un solo uso, con caducidad automática a las 24 horas y consumo
    atómico frente a condiciones de carrera (FR-006/FR-007). El nuevo miembro queda con nivel de
    permisos `MEM`.
  - Bloqueo anti-fuerza-bruta de introducción de códigos de invitación (5 intentos fallidos → 15
    min, reseteo automático del contador al expirar) — mismo patrón que el bloqueo de login de
    `001-login-skeleton` (FR-013).
  - Registro de auditoría de cada intento de introducir un código de invitación (éxito, fallo o
    bloqueado) en `household_invitation_attempts_log`, con retención de 90 días (FR-015).
- Modelo de datos: tablas nuevas `household_invitations` y `household_invitation_attempts_log`;
  columnas nuevas `failed_invite_attempts`/`invite_locked_until` en `users` (migración puramente
  aditiva, UAT humana confirmada antes de aplicarse sobre datos ya existentes — ver
  `alembic/versions/7b11fd5522de_household_invitations_y_bloqueo_de_.py`).
- `scripts/purge_household_invitation_attempts_log.py`: purga las filas de auditoría de intentos de
  código de invitación con más de 90 días, mismo patrón que `scripts/purge_login_audit_log.py`.

### Security

- El código de invitación a un hogar nunca se almacena en claro: hash HMAC-SHA256 con un secreto de
  aplicación nuevo (variable de entorno `INVITE_CODE_HMAC_SECRET`), determinista para permitir
  búsqueda indexada por igualdad sin sacrificar la irreversibilidad del valor almacenado
  (ADR-0006, vault de Obsidian).
- `username`/`email` restringidos a caracteres ASCII en el registro abierto (FR-011), para evitar
  homóglifos y una comparación insensible a mayúsculas inconsistente entre alfabetos — refuerzo del
  criterio ya asumido en `001-login-skeleton` ahora que el alta es un formulario público, no un
  script operado por alguien de confianza.

## [0.1.0] - 2026-08-25

### Added

- Esqueleto de login end-to-end (FastAPI + Jinja2 + PostgreSQL) — feature `001-login-skeleton`:
  - Login con username o email + contraseña, página de bienvenida y logout.
  - Hash de contraseñas con Argon2id (ADR-0002, vault de Obsidian).
  - Sesión de servidor única por usuario (token opaco, UPSERT en cada login).
  - Bloqueo anti-fuerza-bruta por usuario (5 intentos fallidos → 15 min, reseteo automático al
    expirar), con protección real frente a condiciones de carrera (`SELECT ... FOR UPDATE`).
  - Registro de auditoría de cada intento de login (éxito, fallo o bloqueado), con retención de
    90 días.
- Modelo de datos base: `keys_catalog`, `households`, `users`, `user_sessions`,
  `login_audit_log` (migración Alembic inicial).
- `scripts/seed_user.py`: crea un usuario de prueba con la contraseña ya hasheada.
- `scripts/purge_login_audit_log.py`: purga las filas de auditoría con más de 90 días.
- CI: servicio PostgreSQL y paso `ty check` en el pipeline de calidad
  (`.github/workflows/ci.yml`).

### Security

- Mitigación de enumeración de usuarios por medición de tiempo (timing attack) en el login,
  verificando siempre un hash aunque el identificador no exista (ADR-0004, vault de Obsidian).
- Detección correcta del esquema HTTPS (para la cookie de sesión `Secure`) cuando la aplicación
  corre detrás de un proxy inverso, confiando únicamente en orígenes configurados como fiables
  (ADR-0003, vault de Obsidian).
- `session_token` se almacena en claro en `user_sessions`; riesgo evaluado y aceptado
  conscientemente para el volumen de esta feature (ADR-0005, vault de Obsidian).
