# Phase 0 — Research: 002-user-registration-households

## 1. Generación del código de invitación

**Decision**: `secrets.choice()` (stdlib, mismo módulo que ya genera el token de sesión en
`auth/session.py`) sobre un alfabeto alfanumérico de 32 símbolos que excluye caracteres ambiguos al
transcribir a mano: se descartan `0`/`O`, `1`/`I`/`l` (dígitos y letras que se confunden entre sí en
muchas fuentes tipográficas). 8 caracteres (longitud ya fijada en la spec, 1ª pasada de
`/speckit.clarify`).

**Rationale**: FR-007 exige que el código se "introduzca a mano" — al ser para transcripción humana
(de viva voz, WhatsApp, SMS), la legibilidad importa más que maximizar el espacio de posibilidades.
`secrets.choice()` usa el generador criptográficamente seguro del sistema operativo (a diferencia de
`random.choice()`), coherente con que el código protege el acceso a un hogar. Con 32 símbolos y 8
posiciones el espacio es 32⁸ ≈ 1.1×10¹² combinaciones — suficiente margen frente al bloqueo de 5
intentos (FR-013) y la caducidad de 24h (FR-006), que son las defensas reales contra fuerza bruta
(ver ADR-0006, "Se sacrifica").

**Alternatives considered**:
- Alfabeto completo (36 símbolos, incluyendo los ambiguos): más espacio de posibilidades, pero peor
  UX de transcripción manual — un código mal leído (`0` vs `O`) obliga a repetir el intento y consume
  el contador de FR-013 sin que sea un ataque real.
- Base32 (RFC 4648, ya sin ambigüedad por diseño): equivalente en la práctica al alfabeto filtrado
  elegido; se descarta solo por no aportar nada sobre una lista explícita ya construida a mano, sin
  necesitar una dependencia ni una codificación adicional.

## 2. Hash del código de invitación

**Decision**: `hmac.new(secret, code.encode(), hashlib.sha256).hexdigest()` (ambos módulos de la
librería estándar — sin dependencia nueva), con `secret` leído de la variable de entorno
`INVITE_CODE_HMAC_SECRET` (`.env`, no versionada). Comparación en verificación con
`hmac.compare_digest()` (constante en tiempo, evita timing attacks al comparar el hash calculado
contra `household_invitations.code_hash`).

**Rationale**: Decisión de arquitectura ya fijada en `ADR-0006` (Aceptado) — determinista, permite
`WHERE code_hash = ?` indexado, sin reutilizar Argon2id fuera de su caso de uso correcto. Aquí solo se
documenta la implementación concreta: no se necesita ninguna librería de terceros porque `hmac` y
`hashlib` ya cubren HMAC-SHA256 en la librería estándar de Python.

**Alternatives considered**: ver ADR-0006 (Argon2id, SHA-256 sin clave) — ya descartadas ahí, no se
repite el análisis.

## 3. Flujo post-registro: ¿auto-login o formulario de login separado?

**Decision**: Auto-login inmediato tras un registro exitoso — se reutiliza directamente
`auth/session.create_session()` (mismo mecanismo que usa `POST /login`) al final de `POST /register`,
sin exigir que el usuario vuelva a introducir sus credenciales.

**Rationale**: FR-009 exige que la cuenta quede activa "sin ningún paso adicional" tras el registro;
SC-001 mide el registro completo en <2 minutos. Pedir un segundo formulario de login inmediatamente
después de que el usuario ya introdujo su contraseña en el registro sería un paso redundante que no
aporta valor de seguridad (la contraseña ya se validó por construcción, es la que el propio usuario
acaba de elegir) y solo añadiría fricción medible contra SC-001. `create_session()` ya es
reutilizable tal cual — no requiere ningún cambio en `auth/session.py`.

**Alternatives considered**:
- Redirigir a `GET /login` tras el registro, sin autenticar: más simple de razonar (un único punto de
  entrada a la sesión), pero contradice la lectura más natural de FR-009 ("sin ningún paso
  adicional") y penaliza SC-001 sin ningún beneficio de seguridad compensatorio.

## 4. Bloqueo por intentos fallidos de código de invitación (FR-013)

**Decision**: Nuevo módulo `auth/invite_lockout.py`, mismo patrón exacto que `auth/lockout.py` de
001 (`check_lockout`/`register_failed_attempt`/`reset_lockout`), pero operando sobre
`failed_invite_attempts`/`invite_locked_until` en vez de `failed_login_attempts`/`locked_until`, y
sin duración propia distinta: 15 minutos, 5 intentos — mismos valores que FR-007 de 001 (mismo
patrón, ver spec → Clarifications).

**Rationale**: FR-013 se decidió explícitamente en la 2ª pasada de `/speckit.clarify` como "mismo
patrón que FR-007 de 001-login-skeleton" — no es una decisión de diseño abierta, es una réplica
intencionada. `register_failed_attempt()` reutiliza el mismo `SELECT ... FOR UPDATE` que 001 (ver
`tests/unit/test_lockout.py`/`test_lockout_concurrency.py` de 001 como referencia directa de patrón
de test a replicar en `test_invite_lockout.py`/`test_invite_lockout_concurrency.py`).

**Alternatives considered**: extender `lockout.py` existente con un parámetro que seleccione qué par
de columnas operar, en vez de un módulo nuevo — descartado por simplicidad de lectura: mezclar dos
conceptos de bloqueo distintos (login vs. código de invitación) en una función parametrizada añade
una rama condicional a un módulo hoy trivial, sin ahorrar código real (la lógica es de 10 líneas).

## 5. Auditoría de intentos de código de invitación (FR-015)

**Decision**: Nuevo módulo `auth/invite_audit.py` con `record_invite_attempt(db, *, user_id,
household_id, result)`, mismo patrón que `auth/audit.py` de 001 (`record_login_attempt`), escribiendo
en `household_invitation_attempts_log`.

**Rationale**: FR-015 se decidió explícitamente durante `/speckit.plan` (hallazgo de `db-designer`
sobre el hueco de FR-012, aprobado por el humano) como tabla simétrica a `login_audit_log` — misma
justificación de reutilizar el patrón ya validado en 001 que en el punto 4.

**Alternatives considered**: ninguna — es una réplica directa de un patrón ya aprobado, no había
alternativa de diseño abierta que evaluar aquí.

## 6. Purga de `household_invitation_attempts_log` (retención 90 días, FR-015)

**Decision**: Script nuevo `scripts/purge_household_invitation_attempts_log.py`, mismo patrón que
`scripts/purge_login_audit_log.py` de 001 (`DELETE ... WHERE occurred_at < now() - interval '90
days'`).

**Rationale**: FR-015 fija la misma retención de 90 días que FR-012 de 001 explícitamente ("mismo
patrón que el registro de auditoría de login"). Replicar el script ya existente es más simple que
generalizarlo con un parámetro de tabla, dado que ambos scripts son invocaciones puntuales (cron/tarea
programada fuera del alcance de esta feature), no un módulo de librería compartido.

**Nota — `household_invitations` no tiene script de purga propio en esta feature**: a diferencia del
log de intentos, la spec no fija una política de retención para las filas ya usadas/caducadas de
`household_invitations` (solo exige que dejen de ser válidas para asociarse, no que se borren). Se
deja fuera de alcance — el volumen esperado (generación de códigos es un evento poco frecuente, ver
`data-model.md` → Índices) hace que una tabla sin purgar durante la vida del proyecto no sea un
problema real a este volumen.

## 7. Estrategia de testing

**Decision**: Sin cambios respecto a `001-login-skeleton` — mismo `pytest` +
`starlette.testclient.TestClient` contra `TEST_DATABASE_URL` (PostgreSQL real), misma fixture
`tests/conftest.py` (migra con Alembic al inicio de sesión, aplica también a las tablas nuevas de
esta feature sin cambios en el fixture). Mismo patrón de aislamiento (`db_session` con
savepoint/rollback para la mayoría de tests) y la misma excepción para concurrencia real (`db_engine`
sin envolver, para `test_invite_lockout_concurrency.py` — réplica directa del patrón ya validado y
documentado en `specs/001-login-skeleton/research.md` §5 para `test_lockout_concurrency.py`, incluida
la técnica de "bloqueo observado directamente" con `threading.Event` en vez de `sleep`/polling, y el
interlineado manual sin hilos para el control negativo).

**Rationale**: No hay ninguna incógnita nueva de testing en esta feature — reutiliza íntegramente la
infraestructura y los patrones ya validados y documentados en 001, incluida la corrección ya
descubierta sobre por qué el control negativo de concurrencia no puede depender de una señal de
"commit ya ocurrido" entre hilos.

**Alternatives considered**: ninguna — no hay justificación para desviarse del patrón ya probado.
