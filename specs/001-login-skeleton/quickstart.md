# Quickstart / UAT: 001-login-skeleton

Guion de validación end-to-end. Cubre SC-004 (verificación humana sin conocer la implementación
interna) y sirve de base para el guion de UAT formal que se entregará antes de `/speckit.converge`
(obligatorio para todo flujo user-facing, según `01_estilo_comportamiento.md`).

## Prerrequisitos

- PostgreSQL local en marcha: `net start postgresql-x64-18`.
- `.env` con `DATABASE_URL` apuntando a la base de datos del proyecto (no versionado — crear el
  propio si no existe).
- Dependencias instaladas: `uv sync`.
- Migraciones aplicadas: `uv run alembic upgrade head` (crea `keys_catalog`, `households`, `users`,
  `user_sessions`, `login_audit_log`, y siembra el grupo `NUS` — ver `data-model.md`).

## Setup: usuario de prueba

Esta feature no incluye registro (FR-011): el usuario de prueba se inserta directamente, fuera del
flujo de la aplicación. Ejemplo (ejecutar en `psql` o script equivalente, con el hash ya calculado
vía `argon2-cffi` — no insertar la contraseña en texto plano):

```sql
INSERT INTO users (username, email, password_hash, first_name, permission_level_code)
VALUES ('jdoe', 'jdoe@example.com', '<hash argon2id de Segura123!>', 'Jane', 'MEM');
```

## Arrancar el servidor

```bash
uv run uvicorn financial_health_app.main:app --reload
```

Abrir `http://localhost:8000/login`.

## Escenarios a validar (mapeados a `spec.md`)

### 1. Login correcto (US1)

1. Introducir `jdoe` (o `jdoe@example.com`) + `Segura123!`.
2. **Esperado**: redirección a la página de bienvenida en <3s, mostrando "Jane" (SC-001).
3. Pulsar "Cerrar sesión".
4. **Esperado**: redirección a `/login`.
5. Intentar navegar directamente a `/`.
6. **Esperado**: redirección a `/login` (sin sesión activa, FR-005).

### 2. Credenciales inválidas (US2)

1. Introducir `jdoe` + una contraseña incorrecta.
2. **Esperado**: mensaje de error genérico, sin especificar qué campo falló (FR-006); no se crea
   sesión (verificar que `/` sigue redirigiendo a `/login`).
3. Introducir un identificador que no existe (p. ej. `noexiste`) + cualquier contraseña.
4. **Esperado**: mismo mensaje de error genérico que en el paso 2 (SC-002).

### 3. Bloqueo anti-fuerza-bruta (US3)

1. Introducir la contraseña incorrecta de `jdoe` 5 veces seguidas.
2. **Esperado**: al 6º intento, incluso con la contraseña correcta, el login se rechaza (SC-003) con
   el mismo mensaje de error genérico que un intento con password incorrecta (FR-006) — no un mensaje
   distinto de "bloqueado"; el estado de bloqueo solo es distinguible por tiempo de respuesta, no por
   el texto mostrado (SC-002, ADR-0004).
3. Esperar 15 minutos (o, en entorno de test, ajustar el reloj/backdatear `locked_until` en BD para
   no esperar en tiempo real).
4. Reintentar login con la contraseña correcta.
5. **Esperado**: login exitoso — el contador se reseteó automáticamente al expirar el bloqueo, sin
   haber necesitado un login correcto previo (spec → Clarifications).

### 4. Sesión única (Clarifications)

1. Hacer login como `jdoe` en un navegador/pestaña A.
2. Hacer login como `jdoe` en un navegador/pestaña B (distinta cookie).
3. Volver a la pestaña A y refrescar `/`.
4. **Esperado**: la pestaña A es redirigida a `/login` (su sesión quedó invalidada por el login de B).

### 5. Auditoría (FR-012)

1. Tras los escenarios anteriores, consultar `login_audit_log` (`SELECT * FROM login_audit_log ORDER
   BY occurred_at DESC`).
2. **Esperado**: una fila por cada intento realizado (éxitos, fallos y bloqueados), con
   `attempted_identifier`, `result` y `occurred_at` coherentes con lo ejercitado.

## Resultado esperado global

Los 5 escenarios pasan sin intervención manual en el código ni en la base de datos más allá de lo
descrito (setup del usuario semilla y, opcionalmente, ajustar `locked_until` para no esperar 15
minutos reales en el escenario 3).
