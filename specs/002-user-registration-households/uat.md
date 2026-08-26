# UAT: 002-user-registration-households

## Prerrequisitos

- PostgreSQL local en marcha: `net start postgresql-x64-18`.
- `.env` con `DATABASE_URL` y, nuevo en esta feature, `INVITE_CODE_HMAC_SECRET` (cualquier cadena
  aleatoria larga, p. ej. generada con `python -c "import secrets; print(secrets.token_hex(32))"` —
  ver ADR-0006).
- Dependencias instaladas: `uv sync` (sin dependencias nuevas respecto a `001`).
- Migraciones aplicadas: `uv run alembic upgrade head` (crea `household_invitations`,
  `household_invitation_attempts_log`, y añade `failed_invite_attempts`/`invite_locked_until` a
  `users` — ver `data-model.md`).

### Resultado 

Todo según lo esperado. 

Mejora: Se ha comprobado que la tabla `users` ha generado un campo `permission_level_group` que siempre tiene el valor "NUS" debido al campo por el que unir en la tabla `keys_catalog`. Sin embargo, sería mejor que la información acerca del grupo permaneciera en los metadatos de la tabla ya que de esta forma ahorramos el espacio de un campo que no genera ninguna utilidad. Esto sería recomendable extrapolarlo a todos los campos que usen equivalencias de la tabla `keys_catalog`. 

## Arrancar el servidor

```bash
uv run uvicorn financial_health_app.main:app --reload
```

### Resultado 

Todo según lo esperado.

## Escenarios a validar (mapeados a `spec.md`)

### 1. Alta de un nuevo usuario (US1)

1. Abrir `http://localhost:8000/register`.
2. Completar el formulario con datos nuevos (username/email no usados antes) y una contraseña de al
   menos 8 caracteres.
3. **Esperado**: redirección a la página de bienvenida, ya autenticado, sin tener que volver a hacer
   login por separado (FR-009, auto-login) — en menos de 2 minutos en condiciones normales (SC-001).
4. Repetir el registro con el mismo `username` o `email`.
5. **Esperado**: el sistema rechaza el registro indicando explícitamente que ya está en uso, sin
   crear una cuenta duplicada (FR-002, SC-002).
6. Intentar registrarse con una contraseña de menos de 8 caracteres.
7. **Esperado**: error de validación antes de persistir nada (FR-011).
    - Necesario un mensaje que indique que ha fallado en el registro para poderlo hacer bien.

### 2. Creación de un hogar nuevo (US2)

1. Con el usuario recién registrado (sin hogar), ir a `/household`.
2. Crear un hogar indicando un nombre.
3. **Esperado**: el usuario queda asociado como administrador (`ADM`) en menos de 1 minuto (SC-003).
4. Intentar crear un segundo hogar desde la misma cuenta.
5. **Esperado**: rechazado — un usuario pertenece como máximo a un hogar a la vez (FR-008).

### 3. Generar un código de invitación y asociarse desde otra cuenta (US3)

1. Desde la cuenta con hogar, en `/household`, generar un código de invitación.
2. **Esperado**: se muestra el código en claro una única vez (8 caracteres alfanuméricos, sin `0`,
   `O`, `1`, `I`, `l`).
3. Registrar una segunda cuenta nueva (repetir escenario 1) y, desde `/household` sin hogar,
   introducir el código generado en el paso 1.
4. **Esperado**: la segunda cuenta queda asociada al mismo hogar con nivel `MEM` (no administrador),
   en menos de 1 minuto (SC-004). El código deja de funcionar si se vuelve a introducir (un solo
   uso).
5. Esperar a que caduque un código sin usar (o backdatear `expires_at` en BD para no esperar 24h
   reales) e intentar usarlo.
6. **Esperado**: rechazado con mensaje de error genérico, igual que un código inexistente.

### 4. Bloqueo anti-fuerza-bruta de códigos (FR-013)

1. Desde una cuenta sin hogar, introducir 5 códigos incorrectos consecutivos en `/household`.
2. **Esperado**: al 6º intento, incluso con un código correcto, el sistema lo rechaza durante 15
   minutos (SC-006).
3. Esperar 15 minutos (o backdatear `invite_locked_until` en BD) y reintentar con un código válido.
4. **Esperado**: éxito — el contador se reseteó automáticamente al expirar el bloqueo, sin necesitar
   un intento correcto previo.

### 5. Auditoría (FR-015)

1. Tras los escenarios anteriores, consultar `household_invitation_attempts_log` (`SELECT * FROM
   household_invitation_attempts_log ORDER BY occurred_at DESC`).
2. **Esperado**: una fila por cada intento realizado (éxitos, fallos y bloqueados), con `user_id`,
   `household_id` (NULL cuando no aplica), `result` y `occurred_at` coherentes con lo ejercitado.

## Resultado esperado global

Los 5 escenarios pasan sin intervención manual en el código ni en la base de datos más allá de lo
descrito (generación de `INVITE_CODE_HMAC_SECRET` y, opcionalmente, ajustar `expires_at`/
`invite_locked_until` para no esperar en tiempo real).
