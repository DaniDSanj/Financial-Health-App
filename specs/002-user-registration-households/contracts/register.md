# Contract: registro de usuario

Aplicación FastAPI + Jinja2 (SSR): respuestas HTML renderizado, no JSON — mismo criterio que
`contracts/login.md` de `001-login-skeleton`.

## `GET /register`

- **Auth**: ninguna requerida. Si ya hay sesión activa válida, redirige (`303`) a `GET /`.
- **Response 200**: página HTML con formulario de registro (campos `first_name`, `last_name`
  [opcional], `username`, `email`, `password`).

## `POST /register`

- **Auth**: ninguna requerida.
- **Request** (form-encoded): `first_name` (string, requerido), `last_name` (string, opcional),
  `username` (string, requerido), `email` (string, requerido), `password` (string, requerido).
- **Validación de entrada** (antes de tocar la base de datos, FR-011):
  - Todos los campos requeridos no vacíos → si falta alguno, `422`/re-render con error de validación.
  - `email` con formato válido → si no, `422`/re-render.
  - `password` con longitud entre 8 y 128 caracteres (FR-011, sin requisito de composición) → si no,
    `422`/re-render.
  - `username` ≤ 50 caracteres, `email` ≤ 255 caracteres, `first_name` ≤ 100 caracteres, `last_name`
    ≤ 50 caracteres (FR-011, mismos límites ya fijados en el modelo de datos de
    `001-login-skeleton`) → si alguno los excede, `422`/re-render; el valor NUNCA se trunca en
    silencio.
  - `username` y `email` DEBEN ser ASCII (FR-011) → si contienen cualquier carácter fuera de ese
    rango, `422`/re-render.
- **Comportamiento**:
  1. Comprobar unicidad de `username`/`email` (`LOWER(username) = LOWER(:username) OR LOWER(email) =
     LOWER(:email)`, mismo criterio insensible a mayúsculas que FR-002/FR-010 de 001).
     - Si ya existe: **Response 409** (conflicto) — re-render del formulario indicando explícitamente
       que el username o email ya está en uso (FR-002; a diferencia del login, aquí sí se distingue
       la causa — no es un flujo de autenticación con riesgo de enumeración de cuentas existentes por
       el lado del login, sino de alta).
  2. Hashear `password` con `auth/hashing.hash_password()` (Argon2id, reutilizado de 001 sin
     cambios — FR-003).
  3. Insertar fila en `users` (`household_id = NULL`, `permission_level_group = 'NUS'`,
     `permission_level_code = 'MEM'` por defecto hasta que cree/se asocie a un hogar — sin
     significado real todavía, ver spec → Assumptions). **Capturar `IntegrityError`** en este
     `INSERT` (violación de `ix_users_username_lower`/`ix_users_email_lower`) y traducirla a
     **Response 409**, con el mismo mensaje que el paso 1 — la comprobación previa por `SELECT` cubre
     el caso común, pero dos peticiones simultáneas con el mismo username/email pueden pasarla ambas
     antes de que cualquiera haga commit; sin esta captura, la petición perdedora de esa carrera
     devolvería un `500` no controlado en vez del `409` que el Edge Case de `spec.md` promete.
  4. Crear sesión inmediatamente (`auth/session.create_session()`, mismo mecanismo que login —
     FR-009, auto-login, ver `research.md` §3).
  5. Fijar cookie de sesión (mismos atributos que `POST /login`: `HttpOnly`, `Secure` si HTTPS,
     `SameSite=Lax`).
  6. **Response 303** → redirige a `GET /` (página de bienvenida, ahora sin hogar asociado — ver
     `contracts/household.md` para el siguiente paso opcional).

## Códigos de estado usados

| Código | Cuándo |
|---|---|
| 200 | Formulario renderizado correctamente (`GET /register`) |
| 303 | Redirección tras registro exitoso, o por sesión ya activa |
| 409 | `username` o `email` ya en uso (FR-002) — detectado por el `SELECT` previo, o por `IntegrityError` en el `INSERT` si dos peticiones simultáneas ganan la carrera al `SELECT` |
| 422 | Formulario enviado con campos vacíos, email inválido, contraseña fuera del rango 8-128 caracteres, `username`/`email`/`first_name`/`last_name` que excede su longitud máxima, o `username`/`email` con caracteres fuera de ASCII (FR-011) |
