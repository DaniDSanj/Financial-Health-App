# Contract: endpoints de login / logout / bienvenida

Aplicación FastAPI + Jinja2 (SSR): los endpoints devuelven HTML renderizado, no JSON. "Contrato" aquí
describe rutas, método, parámetros, códigos de estado y el comportamiento observable — no un esquema
de API pública para consumidores externos (no existen en esta feature).

## `GET /login`

- **Auth**: ninguna requerida. Si ya hay sesión activa válida (cookie de sesión presente y no
  expirada), redirige (`303`) a `GET /`.
- **Response 200**: página HTML con formulario de login (campos `identifier`, `password`).

## `POST /login`

- **Auth**: ninguna requerida.
- **Request** (form-encoded, no JSON — formulario HTML estándar): `identifier` (string, username o
  email), `password` (string).
- **Validación de entrada**: ambos campos no vacíos → si falta alguno, `422`/re-render del formulario
  con error de validación, sin consultar la base de datos (spec → Edge Cases).
- **Comportamiento**:
  1. Buscar usuario por `LOWER(username) = LOWER(:identifier) OR LOWER(email) = LOWER(:identifier)`.
  2. Si no existe usuario **o** `locked_until` está en el futuro **o** la contraseña no verifica:
     - Si el usuario no existe: invocar igualmente `verify_password_timing_safe(password, None)`
       (verificación Argon2id contra un hash dummy precalculado) antes de responder, para que el
       tiempo de respuesta sea equivalente al de una password incorrecta contra un usuario real y no
       se pueda distinguir "usuario no existe" de "password incorrecta" por timing (mitigación de
       enumeración de usuarios, SC-002, ADR-0004).
     - Registrar evento en `login_audit_log` (`result` = `'failure'` si no existe usuario o password
       incorrecta pero no bloqueado; `'locked'` si el usuario existe y está bloqueado).
     - Si existe usuario y no estaba bloqueado y la password fue incorrecta: incrementar
       `failed_login_attempts`; si llega a 5, fijar `locked_until`.
     - **Response 401**: re-render del formulario con el mensaje de error genérico único ("Usuario o
       contraseña incorrectos" — FR-006), sin distinguir causa.
  3. Si `locked_until` ya expiró (pasado): resetear `failed_login_attempts = 0`, `locked_until = NULL`
     antes de continuar con la verificación de password (spec → Clarifications, reseteo automático).
  4. Si las credenciales son válidas y no hay bloqueo activo:
     - `UPSERT` en `user_sessions` (nuevo `session_token`, `expires_at = now() + 24h`), invalidando
       cualquier sesión anterior del mismo usuario (FR-004).
     - Resetear `failed_login_attempts = 0`, `locked_until = NULL`.
     - Registrar evento en `login_audit_log` (`result = 'success'`).
     - Fijar cookie de sesión (`HttpOnly`, `Secure` si la petición llega por HTTPS, `SameSite=Lax`).
     - **Response 303** → redirige a `GET /`.

## `POST /logout`

- **Auth**: requiere sesión activa válida (si no hay, `303` → `GET /login`).
- **Comportamiento**: borra la fila de `user_sessions` del usuario; expira la cookie de sesión.
- **Response 303** → redirige a `GET /login`.

## `GET /` (página de bienvenida)

- **Auth**: requiere sesión activa válida — si no hay cookie de sesión, o el token no existe en
  `user_sessions`, o `expires_at` ya pasó: **Response 303** → redirige a `GET /login` (FR-005).
- **Comportamiento si hay sesión válida**: desliza `expires_at = now() + 24h` (ventana de
  inactividad).
- **Response 200**: página HTML de bienvenida mostrando `first_name` del usuario autenticado (FR-008)
  y un formulario/botón que envía `POST /logout` (FR-009).

## Códigos de estado usados

| Código | Cuándo |
|---|---|
| 200 | Página renderizada correctamente (GET /login, GET /) |
| 303 | Redirección tras acción exitosa o por falta de autorización (patrón POST-Redirect-GET) |
| 401 | Credenciales incorrectas o usuario bloqueado (re-render de /login con error) |
| 422 | Formulario de login enviado con campos vacíos |
