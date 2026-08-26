# Feature Specification: Registro de usuarios y gestión de hogares

**Feature Branch**: `002-user-registration-households`

**Created**: 2026-08-25

**Status**: Draft

## Clarifications

### Session 2026-08-25

- Q: ¿El registro es abierto a cualquier visitante, o requiere invitación previa de un miembro ya existente? → A: Registro abierto — cualquiera puede crear una cuenta libremente, igual que puede crear su propio hogar; solo unirse a un hogar *ya existente* (creado por otro miembro) requiere invitación.
- Q: ¿Cómo se une un usuario a un hogar creado por otro? → A: Código de invitación generado por el hogar; el nuevo miembro lo introduce para asociarse. De un solo uso (se invalida tras la primera asociación exitosa).
- Q: ¿La cuenta se activa de inmediato tras el registro, o requiere verificar el email antes del primer login? → A: Activación inmediata, sin verificación de email (coherente con el perfil de riesgo bajo ya asumido en `001-login-skeleton`; no se introduce infraestructura de envío de emails en esta feature).
- Q: ¿Cuál es el requisito mínimo de complejidad de contraseña en el registro? → A: Longitud mínima de 8 caracteres, sin requisito de composición (sin exigir mayúsculas/números/símbolos), alineado con NIST 800-63B.
- Q: ¿Crear/unirse a un hogar (US2/US3) forma parte del mismo flujo que el registro (US1), o es un paso separado y posterior? → A: Separado — el registro (US1) termina dejando al usuario autenticado sin hogar; crear o unirse a un hogar es una acción posterior, accesible desde su cuenta cuando el usuario quiera, no un paso obligatorio del formulario de registro.
- Q: ¿El formulario de registro abierto (FR-004) necesita alguna protección anti-abuso (throttling/CAPTCHA) contra creación masiva de cuentas? → A: No, fuera de alcance de esta feature — mismo criterio que el throttling por IP ya descartado para el login en `001-login-skeleton`; se revisa en una feature de seguridad posterior si el riesgo lo justifica.
- Q: Además de invalidarse al usarse, ¿el código de invitación a un hogar caduca por tiempo si nadie lo usa? → A: Sí, caduca automáticamente pasadas 24 horas si nadie lo ha usado.
- Q: ¿Qué forma tiene el código de invitación? → A: Código alfanumérico corto (p. ej. 8 caracteres) que el usuario introduce a mano en un campo del formulario — no un enlace/URL con token largo.
- Q: El código de invitación de 8 caracteres es adivinable por fuerza bruta si nadie limita los intentos. ¿Qué protección se aplica? → A: Bloqueo de 15 minutos tras 5 intentos fallidos consecutivos, mismo patrón que FR-007 de `001-login-skeleton` para el login.
- Q: ¿Cómo se almacena el código de invitación en base de datos? → A: Hasheado (no reversible), mismo criterio que las contraseñas — nunca en texto plano.
- Q: ¿El nombre del hogar (indicado al crearlo, US2) debe ser único en toda la plataforma? → A: No, es solo una etiqueta libre; puede repetirse entre hogares distintos.

**Input**: User description: "Registro de usuarios y gestión de hogares (feature 002, sigue a 001-login-skeleton). Contexto: 001-login-skeleton dejó explícitamente fuera de alcance el registro de usuarios, la recuperación de contraseña, la gestión de hogares y el 2FA. El modelo de datos ya tiene `households` (con `users.household_id` FK nullable, sin gestión propia todavía) y `users.permission_level_code` (ADM/MEM/VIS, poblado pero sin ninguna funcionalidad que lo use). Los únicos usuarios existentes hoy se crean vía `scripts/seed_user.py` — no hay alta real. Alcance funcional propuesto: alta de usuario (self-registration) que sustituye/complementa el script de seed; creación de hogar por un usuario, que queda asociado a él; asociación a un hogar existente creado por otro miembro; posible primer uso real de `permission_level_code` para decidir quién puede invitar/gestionar miembros. Explícitamente fuera de alcance: recuperación de contraseña y 2FA (ambos diferidos). Continuidad técnica con 001: mismo stack (FastAPI + Jinja2 SSR, SQLAlchemy 2.0 + psycopg3 sync, Alembic), reutilizar hashing Argon2id y patrón de sesión de `src/financial_health_app/auth/`, mismo patrón de auditoría en tablas/columnas nuevas."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Alta de un nuevo usuario (Priority: P1)

Un visitante sin cuenta rellena un formulario de registro con sus datos básicos (nombre, apellidos, username, email, contraseña) y, tras completarlo, dispone de una cuenta con la que puede iniciar sesión en la plataforma.

**Why this priority**: Es el flujo que sustituye a `scripts/seed_user.py` como única vía de alta hoy existente. Sin esta historia, ninguna de las demás (crear/unirse a un hogar) tiene sentido, porque ambas requieren un usuario ya autenticado.

**Independent Test**: Se puede verificar de forma completamente independiente accediendo al formulario de registro (sin necesidad de invitación ni de ningún usuario previo), completándolo con datos válidos no usados previamente, y comprobando que la cuenta queda creada y permite iniciar sesión de inmediato.

**Acceptance Scenarios**:

1. **Given** que no existe ningún usuario con el username o email introducidos, **When** un visitante completa el formulario de registro con datos válidos, **Then** el sistema crea la cuenta de inmediato y el usuario puede iniciar sesión sin ningún paso adicional (sin invitación previa, sin verificación de email).
2. **Given** un username o email ya registrado por otro usuario, **When** un visitante intenta registrarse con ese mismo valor, **Then** el sistema rechaza el registro indicando que ese username o email ya está en uso, sin crear una cuenta duplicada.
3. **Given** un formulario de registro con una contraseña que no cumple los requisitos de longitud (FR-011), **When** se envía el formulario, **Then** el sistema rechaza la petición con un error de validación antes de persistir nada.

---

### User Story 2 - Creación de un hogar nuevo (Priority: P2)

Un usuario ya autenticado que todavía no pertenece a ningún hogar crea un hogar nuevo y queda asociado a él como su primer miembro.

**Why this priority**: Es el primer uso real de la tabla `households`, que hoy existe en el modelo de datos sin ningún flujo que la gestione. Depende de la Historia 1 (requiere un usuario ya registrado y autenticado).

**Independent Test**: Con un usuario autenticado sin hogar asociado, se puede verificar de forma independiente creando un hogar nuevo desde su cuenta y comprobando que queda asociado a él.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado sin hogar asociado, **When** crea un hogar nuevo indicando un nombre, **Then** el sistema crea el hogar y asocia al usuario como su primer miembro con nivel de permisos administrador.
2. **Given** un usuario autenticado que ya pertenece a un hogar, **When** intenta crear otro hogar, **Then** el sistema rechaza la operación (un usuario pertenece como máximo a un hogar a la vez).

---

### User Story 3 - Asociación a un hogar existente mediante código de invitación (Priority: P3)

Un usuario ya autenticado que todavía no pertenece a ningún hogar introduce un código de invitación generado por un hogar ya existente y queda asociado a ese hogar.

**Why this priority**: Complementa la Historia 2 pero no es imprescindible para que la gestión de hogares aporte valor por sí sola (un usuario puede crear y usar su propio hogar sin que nadie más se una todavía).

**Independent Test**: Con un hogar ya existente y un código de invitación generado por uno de sus miembros, un segundo usuario autenticado sin hogar puede verificar de forma independiente introduciendo ese código y comprobando que queda asociado a ese hogar.

**Acceptance Scenarios**:

1. **Given** un hogar ya existente y un código de invitación alfanumérico corto (8 caracteres) vigente generado por ese hogar, **When** un usuario autenticado sin hogar introduce ese código a mano en el formulario, **Then** el sistema lo asocia al hogar con nivel de permisos miembro (`MEM`, no administrador) y el código queda invalidado para cualquier uso posterior.
2. **Given** un código de invitación ya usado, caducado (más de 24 horas desde su generación) o inexistente, **When** un usuario intenta introducirlo, **Then** el sistema rechaza la asociación con un mensaje de error claro, sin asociar al usuario a ningún hogar.
3. **Given** un usuario que ya pertenece a un hogar, **When** intenta introducir un código de invitación de otro hogar, **Then** el sistema rechaza la operación.
4. **Given** un usuario que ha introducido 5 códigos de invitación incorrectos consecutivos, **When** intenta introducir un sexto código (aunque sea correcto), **Then** el sistema rechaza el intento durante 15 minutos sin verificar el código introducido.

---

### Edge Cases

- ¿Qué ocurre si dos visitantes intentan registrarse simultáneamente con el mismo username o email? → La unicidad la garantiza una restricción de base de datos; el segundo intento en completarse falla con el mismo mensaje de "ya está en uso" de FR-002, independientemente de la simultaneidad.
- ¿Qué ocurre si un mismo usuario envía dos peticiones simultáneas de creación de hogar (p. ej. doble clic) antes de que la primera se confirme? → El sistema garantiza que como máximo una tiene éxito (FR-008); la segunda recibe el mismo error que un usuario que ya tiene hogar, sin dejar ningún hogar huérfano sin miembros asociados.
- ¿Qué ocurre si un usuario sin hogar cierra el formulario de creación/asociación a hogar sin completarlo? → El usuario sigue existiendo y pudiendo iniciar sesión con `household_id` nulo, igual que el comportamiento ya establecido en `001-login-skeleton`; crear o asociarse a un hogar no es obligatorio para poder usar la cuenta.
- ¿Qué ocurre si se introduce un código de invitación inválido, ya usado, caducado (>24h) o inexistente? → El sistema rechaza la asociación con un mensaje de error claro, sin asociar al usuario a ningún hogar (ver también User Story 3, Acceptance Scenario 2).
- ¿Qué ocurre si un usuario ya asociado a un hogar es el único con nivel de permisos administrador y abandona el hogar? → Fuera de alcance de esta feature: no se incluye ningún flujo para abandonar un hogar ni para transferir el nivel de permisos administrador.
- ¿Qué ocurre si un usuario bloqueado por 5 intentos fallidos de código de invitación (FR-013) introduce un código correcto durante el bloqueo? → El intento se rechaza igualmente, sin verificar el código, igual que el patrón ya establecido para el login en `001-login-skeleton` (Edge Cases de esa spec).
- ¿Qué ocurre si dos hogares distintos tienen el mismo nombre? → Es un estado válido: el nombre de hogar no es único en la plataforma (FR-014), solo es una etiqueta para quien lo usa.
- ¿Qué ve un miembro de un hogar si en ese momento no hay ningún código de invitación activo (todos caducados o usados)? → No es un estado especial: el formulario para generar un código nuevo (FR-007) está siempre disponible para cualquier miembro, independientemente de si ya existen otros códigos activos o no.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE exponer un formulario de registro accesible sin sesión activa, con campos para nombre, apellidos, username, email y contraseña. Este formulario NO DEBE incluir ningún paso de creación o asociación a un hogar — el registro termina con el usuario autenticado y sin hogar; crear/unirse a un hogar (FR-005/FR-006) es una acción posterior y opcional, accesible desde su cuenta ya autenticada.
- **FR-002**: El sistema DEBE tratar username y email como campos únicos entre todos los usuarios, con comparación insensible a mayúsculas/minúsculas (mismo criterio que FR-010 de `001-login-skeleton`), y DEBE rechazar el registro si alguno de los dos ya está en uso, indicándolo explícitamente al visitante.
- **FR-003**: El sistema DEBE almacenar la contraseña del nuevo usuario con el mismo mecanismo de hashing ya usado en `001-login-skeleton` (Argon2id vía `src/financial_health_app/auth/hashing.py`), reutilizándolo en vez de reimplementarlo.
- **FR-004**: El sistema DEBE permitir el registro abierto a cualquier visitante, sin requerir invitación previa de ningún miembro ya existente de la plataforma.
- **FR-005**: El sistema DEBE permitir a un usuario autenticado sin hogar asociado crear un hogar nuevo indicando un nombre de hasta 100 caracteres, quedando asociado a él como su primer miembro con nivel de permisos administrador (`ADM`). El nombre NO DEBE estar vacío ni consistir únicamente en espacios en blanco (tras eliminar espacios al inicio/final) — rechazado con error de validación si lo está.
- **FR-006**: El sistema DEBE permitir a un usuario autenticado sin hogar asociado asociarse a un hogar ya existente mediante un código de invitación generado por ese hogar, quedando asociado con nivel de permisos miembro (`MEM`). El código DEBE ser de un solo uso (queda invalidado en cuanto se usa para asociar correctamente a un usuario) y DEBE caducar automáticamente pasadas 24 horas desde su generación si nadie lo ha usado. La validación del código introducido DEBE hacerse por comparación de hash, nunca comparando el valor en claro. Si dos usuarios distintos introducen el mismo código válido de forma simultánea, el sistema DEBE garantizar que como máximo uno de los dos consigue asociarse con él — el otro recibe el mismo error que un código ya usado, sin quedar el hogar con más de una asociación por ese código.
- **FR-007**: El sistema DEBE permitir a cualquier miembro de un hogar generar un código de invitación alfanumérico corto (8 caracteres) para ese hogar, para introducirse a mano en el formulario de asociación (no un enlace/URL). El código en claro DEBE mostrarse una única vez, inmediatamente tras generarse — no queda almacenado en claro en ningún sitio ni es recuperable después de esa respuesta (solo se persiste su hash, FR-006).
- **FR-008**: El sistema DEBE impedir que un usuario que ya pertenece a un hogar cree otro hogar o se asocie a uno distinto mientras siga perteneciendo al primero. Si el mismo usuario envía dos peticiones simultáneas de creación de hogar antes de que la primera se confirme, el sistema DEBE garantizar que como máximo una tiene éxito — la otra recibe el mismo error que un usuario que ya tiene hogar, sin dejar ningún hogar creado sin ningún miembro asociado.
- **FR-009**: El sistema DEBE activar la cuenta de un usuario recién registrado de inmediato, permitiéndole iniciar sesión sin ningún paso adicional (sin verificación de email).
- **FR-010**: El sistema NO DEBE incluir en esta feature recuperación de contraseña olvidada ni autenticación de doble factor — ambas permanecen explícitamente fuera de alcance, como ya se estableció en `001-login-skeleton`.
- **FR-011**: El sistema DEBE validar que el email tiene sintaxis `usuario@dominio` válida (sin verificar que el buzón exista realmente) y exigir una contraseña de al menos 8 caracteres y como máximo 128 (sin requisito adicional de composición — no se exige mezcla obligatoria de mayúsculas, números o símbolos, alineado con NIST 800-63B), rechazando con un error de validación antes de persistir cualquier dato si no se cumplen. `username`/`email`/`first_name`/`last_name` DEBEN respetar los mismos límites de longitud ya fijados en el modelo de datos de `001-login-skeleton` (50/255/100/50 caracteres respectivamente) — un valor que los exceda se rechaza con error de validación, no se trunca en silencio. `username` y `email` DEBEN restringirse a caracteres ASCII — a diferencia de `001-login-skeleton` (donde el único alta era vía `scripts/seed_user.py`, operado por alguien de confianza), el registro abierto de esta feature permite que cualquier visitante anónimo controle este input, por lo que la restricción ASCII ya asumida en 001 se aplica aquí explícitamente por validación de código, evitando homóglifos o comportamiento de comparación insensible a mayúsculas (`LOWER()`) inconsistente entre alfabetos.
- **FR-012**: El sistema DEBE persistir un registro de auditoría de cada alta de usuario y de cada creación/asociación a un hogar (usuario, acción, resultado, marca de tiempo), siguiendo el mismo patrón de campos de auditoría obligatorios ya aplicado a las tablas transaccionales del proyecto.
- **FR-013**: El sistema DEBE bloquear temporalmente (15 minutos) los intentos de un usuario autenticado de introducir códigos de invitación tras 5 intentos fallidos consecutivos, independientemente de si intentos posteriores usan un código correcto — mismo patrón que FR-007 de `001-login-skeleton`. El contador de intentos fallidos DEBE resetearse automáticamente a 0 en cuanto expiran los 15 minutos de bloqueo, sin requerir un intento correcto previo.
- **FR-014**: El nombre de un hogar (indicado al crearlo, FR-005) NO DEBE ser único en la plataforma — hogares distintos pueden compartir el mismo nombre.
- **FR-015**: El sistema DEBE persistir un registro de auditoría de cada intento de introducir un código de invitación (usuario, hogar al que pertenece el código si es identificable, resultado — éxito, fallo o bloqueado —, y marca de tiempo), independiente del contador de intentos fallidos usado para el bloqueo de FR-013 — mismo patrón que el registro de auditoría de login de `001-login-skeleton` (FR-012 de esa spec). El hogar se considera identificable — y por tanto DEBE registrarse — siempre que el código introducido corresponda a una invitación existente, **incluso si ya está usada o caducada**; solo queda sin identificar (campo nulo) si el código no corresponde a ninguna invitación existente en absoluto, o si el intento fue rechazado directamente por bloqueo (FR-013) sin llegar a resolver el código. Los registros DEBEN conservarse durante 90 días y purgarse pasado ese plazo, igual que ese precedente.

### Key Entities *(include if feature involves data)*

- **Usuario**: entidad ya existente (`001-login-skeleton`); esta feature añade su vía real de alta (antes solo vía seed/migración) y activa por primera vez su relación con Hogar y su nivel de permisos.
- **Hogar**: entidad ya existente en el modelo de datos pero sin gestión propia hasta ahora; esta feature añade su creación y la asociación de usuarios a él. Su nombre no es único entre hogares (FR-014).
- **Invitación a hogar**: entidad nueva — código de invitación alfanumérico corto (8 caracteres) asociado a un hogar, generado por uno de sus miembros, almacenado hasheado (nunca en claro). De un solo uso (se invalida al asociar correctamente a un usuario nuevo) y con caducidad automática a las 24 horas de su generación si nadie lo usa antes. Su modelo de datos concreto (columnas exactas) se define en `/speckit.plan`.
- **Intento fallido / bloqueo de código de invitación**: estado asociado a un usuario autenticado que registra sus intentos fallidos consecutivos de introducir un código de invitación y, en su caso, la marca de tiempo hasta la que queda bloqueado — mismo concepto que el bloqueo de login de `001-login-skeleton`, aplicado aquí a la introducción de códigos.
- **Evento de intento de código de invitación (auditoría)**: registro histórico independiente del contador de bloqueo, que guarda cada intento de introducir un código de invitación con su resultado (éxito, fallo o bloqueado) y su marca de tiempo, con fines de auditoría de seguridad (FR-015) — mismo patrón que el evento de login (auditoría) de `001-login-skeleton`. Se conserva 90 días y se purga pasado ese plazo.
- **Nivel de permisos** (`permission_level_code`: `ADM`/`MEM`/`VIS`): columna ya existente en Usuario; esta feature es la primera en asignarlo con significado real (administrador al crear un hogar, miembro al asociarse a uno existente). El nivel `VIS` (solo visualización) no se asigna todavía en ningún flujo de esta feature — queda reservado para uso futuro.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un visitante nuevo completa el registro y dispone de una cuenta utilizable en menos de 2 minutos en condiciones normales.
- **SC-002**: El 100% de los intentos de registro con un username o email ya en uso son rechazados sin crear una cuenta duplicada.
- **SC-003**: Un usuario recién registrado sin hogar puede crear un hogar nuevo y queda asociado a él como administrador en menos de 1 minuto.
- **SC-004**: Un usuario recién registrado sin hogar puede asociarse a un hogar ya existente introduciendo un código de invitación válido en menos de 1 minuto.
- **SC-005**: Un evaluador humano (UAT) puede verificar el flujo completo (registro → creación o asociación a un hogar → login → ver el hogar reflejado en la página de bienvenida) siguiendo un guion de prueba, sin necesidad de conocer la implementación interna.
- **SC-006**: Tras 5 intentos fallidos consecutivos de un usuario introduciendo códigos de invitación, el 100% de los intentos adicionales (incluso con código correcto) son rechazados hasta que expiran los 15 minutos de bloqueo.

## Assumptions

- Un usuario pertenece como máximo a un hogar a la vez, consistente con `users.household_id` ya modelado como FK simple (no relación muchos-a-muchos) en `001-login-skeleton`.
- El primer miembro de un hogar (quien lo crea) recibe automáticamente el nivel de permisos administrador (`ADM`); cualquier miembro que se asocia después a un hogar ya existente recibe el nivel miembro (`MEM`). Esta feature no incluye un flujo para que un administrador cambie el nivel de permisos de otro miembro después de la asociación — queda para una feature posterior si se necesita.
- Seguir sin tener hogar asociado (`household_id` nulo) sigue siendo un estado válido tras esta feature, igual que en `001-login-skeleton`: crear o asociarse a un hogar es opcional, no un paso obligatorio del registro.
- El nivel de permisos `VIS` (solo visualización) queda reservado para uso futuro; ningún flujo de esta feature lo asigna.
- Se reutiliza íntegramente el mecanismo de hashing (Argon2id), el patrón de sesión y las plantillas Jinja2 base ya existentes en `src/financial_health_app/auth/` y `src/financial_health_app/templates/base.html` — esta feature no introduce un mecanismo de autenticación nuevo, solo una vía de alta adicional.
- El código de invitación a un hogar (FR-006/FR-007) es de un solo uso, alfanumérico y corto (8 caracteres, introducido a mano — no un enlace), se almacena hasheado y caduca automáticamente a las 24 horas de su generación si nadie lo usa antes. El alfabeto exacto (p. ej. exclusión de caracteres ambiguos como `0`/`O`, `1`/`l`) y el algoritmo de hash concreto (reutilizando o no el mismo mecanismo Argon2id que las contraseñas) se deciden en `/speckit.plan` sin impacto en el alcance funcional de esta spec.
- El bloqueo por intentos fallidos de código de invitación (FR-013) es por usuario autenticado (quien introduce el código), no por hogar de destino ni por IP — mismo alcance que el bloqueo de login de `001-login-skeleton` (FR-007 de esa spec), sin throttling adicional por IP.
- El formulario de registro abierto (FR-004) no incluye ninguna protección anti-abuso (throttling por IP, CAPTCHA, límite de registros por ventana de tiempo) contra creación masiva de cuentas — mismo criterio que el throttling por IP ya descartado para el login en `001-login-skeleton`; queda como candidato a una feature de seguridad posterior si el riesgo lo justifica.
- El registro es abierto (FR-004): confirmado con el humano (checklist `general.md`, CHK022) que la primera versión de la aplicación se mantiene en un servidor local/ordenador personal, sin exposición pública — igual que ya asumía `001-login-skeleton` para el volumen de uso esperado. Si en una versión futura la app se expone públicamente, abrir el registro sin invitación es un riesgo a revisar en una feature de seguridad posterior (candidato: throttling/CAPTCHA en `POST /register`), no algo a resolver preventivamente ahora sin necesidad real.
- Volumen esperado igual al ya asumido en `001-login-skeleton` (uso doméstico/familiar, decenas de usuarios) — no se establecen requisitos de escalado horizontal para esta feature.
- Sin límite en el número de códigos de invitación activos que un hogar puede tener simultáneamente, ni en el número de miembros de un hogar — mismo criterio que la ausencia de protección anti-abuso ya aceptada para el registro (FR-004) y el bloqueo de códigos (FR-013): quien genera códigos ya es un miembro autenticado del hogar, no un visitante anónimo, así que el riesgo de abuso es marginal al volumen esperado.
- Requisitos de accesibilidad (navegación por teclado, etiquetas para lectores de pantalla) quedan fuera de alcance de esta feature, igual que ya quedaron fuera de `001-login-skeleton` — no hay ningún estándar de accesibilidad fijado todavía en la constitución del proyecto ni en ninguna feature anterior.
- Los intentos de registro fallidos por duplicidad de `username`/`email` (FR-002) NO se persisten en ningún registro de auditoría — a diferencia de los intentos de login (FR-012 de 001) o de código de invitación (FR-015), un intento de registro con un email ya usado no es una señal de seguridad equivalente (no revela si una cuenta existe a un atacante que ya sabe que el registro es abierto) y no alimenta ningún contador de bloqueo; registrar solo altas exitosas es suficiente.
- El campo `apellidos` (`last_name`) del formulario de registro (FR-001) es opcional, no obligatorio
  — coherente con la columna `users.last_name` ya nullable desde `001-login-skeleton` (a diferencia
  de `first_name`, que sí es obligatorio). No se introduce ninguna restricción nueva sobre una
  columna ya existente.
- `permission_level_code = 'MEM'` (valor por defecto asignado a un usuario recién registrado sin hogar todavía, ver FR-001) no implica pertenencia real a ningún hogar — es un valor obligatorio porque la columna es `NOT NULL` desde `001-login-skeleton`, sin significado de autorización hasta que el usuario crea o se asocia a un hogar (FR-005/FR-006). Cualquier feature futura que compruebe niveles de permisos DEBE comprobar también `household_id IS NOT NULL`, no solo `permission_level_code`, para no tratar a un usuario sin hogar como miembro de uno.
- El nombre de hogar acepta cualquier carácter Unicode (sin restricción a ASCII) — a diferencia de `username`/`email`, que si son ASCII por necesitar comparación case-insensitive estable (ver Assumptions de `001-login-skeleton`), el nombre de hogar nunca se compara ni se busca (FR-014: no único), así que no aplica esa misma restricción.
