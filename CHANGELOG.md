# Changelog

Todas las modificaciones notables de este proyecto se documentan en este fichero.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto se adhiere a [Semantic Versioning](https://semver.org/lang/es/).

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
