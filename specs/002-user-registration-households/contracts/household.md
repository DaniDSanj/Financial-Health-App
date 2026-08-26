# Contract: gestión de hogar (crear / unirse / invitar)

Aplicación FastAPI + Jinja2 (SSR): respuestas HTML renderizado, no JSON.

## `GET /household`

- **Auth**: requiere sesión activa válida (si no hay, `303` → `GET /login`, mismo patrón que
  `GET /` de 001).
- **Response 200**:
  - Si el usuario NO tiene `household_id` (FR-001: crear/unirse es posterior y opcional al
    registro): página con dos formularios — crear hogar nuevo (campo `name`) y unirse a uno existente
    (campo `code`).
  - Si el usuario SÍ tiene `household_id`: página con el nombre del hogar, su nivel de permisos
    (`ADM`/`MEM`), y un formulario para generar un nuevo código de invitación (cualquier miembro,
    FR-007) — muestra el código en claro **una sola vez**, inmediatamente tras generarlo (no se
    puede recuperar después, solo se persiste el hash).

## `POST /household/create`

- **Auth**: requiere sesión activa válida.
- **Request** (form-encoded): `name` (string, requerido).
- **Precondición**: el usuario NO debe tener ya un `household_id` (FR-008) → si ya tiene uno,
  **Response 409** (conflicto), sin crear nada.
- **Validación** (FR-005): `name` no vacío, no consistente únicamente en espacios en blanco (tras
  eliminar espacios al inicio/final), y de hasta 100 caracteres → si incumple cualquiera de los 3
  casos, `422`/re-render con error de validación.
- **Comportamiento** (transacción atómica, FR-008 — garantía de concurrencia):
  1. Insertar fila en `households` (`created_by = user_id`).
  2. Actualizar `users` de forma condicional: `UPDATE users SET household_id = :new_household_id,
     permission_level_code = 'ADM' WHERE id = :user_id AND household_id IS NULL` — la condición
     `household_id IS NULL` es la defensa real contra dos peticiones simultáneas del mismo usuario
     (mismo patrón atómico que el consumo de código de invitación en `POST /household/join`).
  3. Si la `UPDATE` afecta **0 filas** (el usuario ya obtuvo un hogar por otra petición concurrente
     entre el paso 1 y el paso 2): **`ROLLBACK`** de toda la transacción — el `INSERT` del paso 1
     queda deshecho, sin dejar ningún hogar huérfano sin miembros — y **Response 409**, mismo error
     que la precondición ya evaluada.
  4. Si la `UPDATE` afecta 1 fila: **`COMMIT`** y **Response 303** → redirige a `GET /household`
     (ahora en la vista "con hogar").

## `POST /household/join`

- **Auth**: requiere sesión activa válida.
- **Request** (form-encoded): `code` (string, requerido, 8 caracteres).
- **Precondición**: el usuario NO debe tener ya un `household_id` (FR-008) → si ya tiene uno,
  **Response 409**, sin validar el código siquiera.
- **Comportamiento**:
  1. Si `users.invite_locked_until` está en el futuro (bloqueo activo, FR-013): registrar intento en
     `household_invitation_attempts_log` (`result = 'locked'`, `household_id = NULL` — no se llega a
     resolver el código), **Response 401**, sin verificar `code`.
  2. Si `invite_locked_until` ya expiró: resetear `failed_invite_attempts = 0`,
     `invite_locked_until = NULL` antes de continuar (mismo reseteo automático que FR-007 de 001).
  3. Calcular `code_hash = HMAC-SHA256(code)` (ADR-0006) y buscar en `household_invitations` una fila
     con ese `code_hash`, `used_at IS NULL` y `expires_at > now()`.
  4. Si no se encuentra ninguna fila (código incorrecto, ya usado, o caducado):
     - Incrementar `failed_invite_attempts`; si llega a 5, fijar `invite_locked_until = now() +
       15min` (`auth/invite_lockout.register_failed_attempt`, mismo patrón `SELECT ... FOR UPDATE`
       que 001).
     - **Búsqueda secundaria, solo para fines de auditoría** (FR-015; no afecta el resultado de la
       petición, que ya es un rechazo): buscar en `household_invitations` una fila con ese
       `code_hash`, **sin** los filtros `used_at IS NULL`/`expires_at > now()`. Si se encuentra, el
       código corresponde a una invitación real ya usada o caducada → identificar `household_id` con
       el de esa fila. Si no se encuentra ninguna fila en absoluto, el código no corresponde a
       ninguna invitación existente → `household_id = NULL`.
     - Registrar intento en `household_invitation_attempts_log` (`result = 'failure'`,
       `household_id` = el identificado por la búsqueda secundaria, o `NULL`).
     - **Response 401** — re-render con mensaje de error genérico ("código inválido o caducado").
  5. Si se encuentra: marcar la invitación como usada (`UPDATE household_invitations SET used_at =
     now(), used_by = :user_id WHERE id = :id AND used_at IS NULL` — atómico, evita doble consumo
     concurrente, ver `data-model.md`).
     - Actualizar `users.household_id` = el del hogar de la invitación, `permission_level_code =
       'MEM'` (FR-006).
     - Resetear `failed_invite_attempts = 0`, `invite_locked_until = NULL`.
     - Registrar intento en `household_invitation_attempts_log` (`result = 'success'`,
       `household_id` = el resuelto).
     - **Response 303** → redirige a `GET /household` (vista "con hogar").

## `POST /household/invite`

- **Auth**: requiere sesión activa válida **y** `household_id` no nulo (cualquier miembro del hogar,
  no solo `ADM` — FR-007 no distingue por nivel de permisos) → si no tiene hogar, **Response 409**.
- **Request**: sin campos (acción de un solo botón).
- **Comportamiento**:
  1. Generar código de 8 caracteres (`auth/invite_code.generate_code()`, alfabeto sin ambiguos —
     `research.md` §1).
  2. Insertar fila en `household_invitations` (`household_id` del usuario, `code_hash` =
     HMAC-SHA256 del código generado, `expires_at = now() + 24h`, `created_by = user_id`).
  3. **Response 200** → re-render de `GET /household` mostrando el código **en claro** una única vez
     (no se persiste ni se puede recuperar después de esta respuesta).

## Códigos de estado usados

| Código | Cuándo |
|---|---|
| 200 | Página renderizada correctamente (`GET /household`, incluida la respuesta con el código recién generado) |
| 303 | Redirección tras crear/unirse a un hogar con éxito |
| 401 | Código de invitación incorrecto, caducado, ya usado, o bloqueado por intentos fallidos (FR-013) |
| 409 | El usuario ya pertenece a un hogar (FR-008) al intentar crear/unirse — detectado por la precondición previa, o por la `UPDATE` condicional afectando 0 filas si dos peticiones de creación compiten — o intenta generar una invitación sin pertenecer a ninguno |
| 422 | `POST /household/create` con `name` vacío, solo espacios en blanco, o de más de 100 caracteres (FR-005) |
