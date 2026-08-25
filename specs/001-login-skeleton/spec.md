# Feature Specification: Esqueleto de login y modelo de datos base

**Feature Branch**: `001-login-skeleton`

**Created**: 2026-08-24

**Status**: Draft

**Input**: User description: "Modelo de datos base más un endpoint mínimo end-to-end (una página o ruta simple) que sirva como esqueleto verificable de FastAPI+Jinja2 funcionando y permita el flujo de un usuario real que sea verificable mediante UAT humana. El flujo debe incluir auth real (login con password, hash con Argon2/bcrypt). Se ofrece un esquema mínimo del modelo de datos en `.specify/memory/db_ideas_001.md` como borrador de partida."

## Clarifications

### Session 2026-08-24

- Q: ¿Se requiere persistir un log de auditoría de los eventos de login (éxito, fallo, bloqueo) más allá del contador de intentos fallidos necesario para el bloqueo (FR-007)? → A: Sí, persistir un registro de auditoría de cada intento de login (usuario, resultado: éxito/fallo/bloqueado, timestamp) además del contador de bloqueo.
- Q: Si un usuario inicia sesión en un segundo dispositivo/navegador mientras ya tiene una sesión activa en otro, ¿qué debe ocurrir? → A: Sesión única — el nuevo login invalida la sesión anterior; solo puede haber una sesión activa por usuario a la vez.
- Q: Pasados los 15 minutos de bloqueo por intentos fallidos (FR-007), ¿cómo se resetea el contador de intentos fallidos? → A: Se resetea automáticamente en cuanto expiran los 15 minutos, sin necesidad de un login correcto.
- Q: El registro de auditoría de login (FR-012) no tiene definida una política de retención. ¿Cuánto tiempo se conservan estos registros? → A: 90 días.
- Q: El bloqueo anti-fuerza-bruta (FR-007) es solo por usuario. ¿Se necesita también throttling por IP en esta feature? → A: No, fuera de alcance de esta feature.

### Session 2026-08-25

- Q: La cookie de sesión debe marcarse Secure/HttpOnly "cuando el entorno lo permita" (Assumptions), pero eso no es verificable. ¿Cuál es el criterio concreto? → A: Detectar el esquema de la petición entrante — Secure se activa si llega por HTTPS.
- Q: La ventana de 24h de inactividad de sesión no define qué cuenta como "actividad" que la desliza. ¿Qué la desliza? → A: Cualquier request autenticado (cualquier petición con sesión válida desliza `expires_at`).
- Q: FR-004 invalida la sesión anterior en un nuevo login (sesión única), pero no define si el usuario de la sesión antigua ve algún aviso. ¿Qué debe ocurrir? → A: Invalidación silenciosa — la sesión antigua se trata igual que cualquier sesión inválida/expirada, sin mensaje específico.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Login con credenciales válidas (Priority: P1)

Un usuario ya dado de alta en la plataforma (creado previamente vía seed/migración, no vía registro — el alta de usuarios no forma parte de esta feature) accede a la página de login, introduce su identificador (username o email) y su contraseña, y accede a una página de bienvenida que confirma que el sistema le reconoce.

**Why this priority**: Es el único flujo de esta feature y el que demuestra que el esqueleto FastAPI + Jinja2 + PostgreSQL funciona end-to-end con autenticación real, no simulada.

**Independent Test**: Con un usuario de prueba ya insertado en la base de datos, se puede verificar completamente accediendo a `/login`, introduciendo las credenciales correctas y comprobando que se llega a la página de bienvenida con el nombre del usuario.

**Acceptance Scenarios**:

1. **Given** un usuario existente con username `jdoe`, email `jdoe@example.com` y contraseña `Segura123!`, **When** introduce `jdoe` (o `jdoe@example.com`) y `Segura123!` en el formulario de login, **Then** el sistema crea una sesión y redirige a la página de bienvenida mostrando su nombre real.
2. **Given** una sesión de login activa, **When** el usuario pulsa "Cerrar sesión", **Then** la sesión se invalida y el usuario es redirigido a la página de login.
3. **Given** un usuario sin sesión activa, **When** intenta acceder directamente a la página de bienvenida, **Then** el sistema lo redirige a la página de login.

---

### User Story 2 - Rechazo de credenciales inválidas (Priority: P2)

Un usuario introduce un identificador o contraseña incorrectos y el sistema se lo comunica sin revelar cuál de los dos campos falló.

**Why this priority**: Es el complemento obligatorio del login exitoso — sin esto, el flujo de auth no es "real". Prioridad P2 porque depende del mismo formulario que P1.

**Independent Test**: Con el mismo usuario de prueba, introducir una contraseña incorrecta y verificar que se muestra un error genérico y no se crea sesión.

**Acceptance Scenarios**:

1. **Given** un usuario existente `jdoe`, **When** introduce su username correcto pero una contraseña incorrecta, **Then** el sistema muestra un mensaje de error genérico ("credenciales incorrectas") sin especificar cuál campo falló, y no crea sesión.
2. **Given** un identificador que no existe en la base de datos, **When** se intenta el login, **Then** el sistema muestra el mismo mensaje de error genérico que en el caso de contraseña incorrecta (para no revelar qué usuarios existen).

---

### User Story 3 - Bloqueo temporal tras intentos fallidos repetidos (Priority: P3)

Tras varios intentos fallidos consecutivos contra el mismo usuario, el sistema bloquea temporalmente los intentos de login para ese usuario, como protección básica contra fuerza bruta.

**Why this priority**: Es una medida de seguridad razonable para un flujo de auth real, pero no bloquea la verificación del esqueleto E2E (US1) ni del rechazo de credenciales (US2); puede probarse de forma independiente.

**Independent Test**: Introducir una contraseña incorrecta 5 veces seguidas contra el mismo usuario y
verificar que el sexto intento (aunque la contraseña sea correcta) es rechazado. El mensaje mostrado
es el mismo mensaje de error genérico de FR-006/SC-002 (no distingue "bloqueado" de "credenciales
incorrectas" por contenido — solo es distinguible por tiempo de respuesta, ver SC-002); lo verificable
de forma independiente en este escenario es que el intento se rechaza y no se crea sesión, no el
texto del mensaje.

**Acceptance Scenarios**:

1. **Given** un usuario existente, **When** se introducen 5 contraseñas incorrectas consecutivas, **Then** el sistema bloquea nuevos intentos de login para ese usuario durante 15 minutos, incluso si la siguiente contraseña introducida es correcta.
2. **Given** un usuario bloqueado temporalmente, **When** transcurren los 15 minutos de bloqueo, **Then** el usuario puede volver a intentar el login con normalidad.

---

### Edge Cases

- ¿Qué ocurre si el usuario introduce el identificador con distinta capitalización (mayúsculas/minúsculas) en username o email? → La comparación de username/email es insensible a mayúsculas/minúsculas; la de contraseña es sensible.
- ¿Qué ocurre si dos usuarios distintos comparten el mismo email pero distinto username, o viceversa? → No está permitido: username y email son ambos únicos en toda la plataforma.
- ¿Qué ocurre si el usuario ya tiene una sesión activa (en otro dispositivo o navegador) y vuelve a hacer login? → La sesión es única por usuario: el nuevo login invalida inmediatamente la sesión anterior, que deja de ser válida aunque su cookie siga presente en el otro dispositivo.
- ¿Qué ocurre si el usuario no tiene hogar asociado (`IDHogar` nulo)? → El login y la página de bienvenida funcionan igualmente; la gestión de hogares queda fuera de esta feature.
- ¿Qué ocurre si el formulario de login se envía con campos vacíos? → El sistema rechaza la petición con un error de validación antes de consultar la base de datos.
- ¿Qué ocurre si el contador de intentos fallidos de un usuario bloqueado recibe un intento adicional durante el bloqueo? → El intento se rechaza inmediatamente por el bloqueo (sin reintentar la verificación de contraseña) y no reinicia el contador de 15 minutos.
- ¿El contador de intentos fallidos requiere un login correcto para resetearse? → No: se resetea automáticamente en cuanto expiran los 15 minutos de bloqueo, aunque el usuario no vuelva a intentar el login inmediatamente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE exponer una página de login accesible sin sesión activa, con campos para identificador (username o email) y contraseña.
- **FR-002**: El sistema DEBE permitir autenticarse indistintamente con el username o con el email del usuario.
- **FR-003**: El sistema DEBE almacenar las contraseñas de los usuarios como hash (Argon2 o bcrypt), nunca en texto plano ni con cifrado reversible.
- **FR-004**: El sistema DEBE crear una sesión de servidor (cookie de sesión) al validar credenciales correctas, y DEBE invalidarla al hacer logout. Cada usuario DEBE tener como máximo una sesión activa simultánea: un nuevo login exitoso invalida cualquier sesión anterior de ese mismo usuario, sin notificación alguna al dispositivo/navegador de la sesión invalidada; si esa sesión antigua se usa después, el sistema la trata igual que cualquier sesión inválida o expirada (redirección a login, sin mensaje distintivo).
- **FR-005**: El sistema DEBE redirigir a login cualquier intento de acceder a la página de bienvenida sin sesión activa.
- **FR-006**: El sistema DEBE mostrar un mensaje de error genérico e idéntico tanto si el identificador no existe como si la contraseña es incorrecta, sin indicar cuál de los dos falló.
- **FR-007**: El sistema DEBE bloquear temporalmente (15 minutos) los intentos de login contra un usuario tras 5 intentos fallidos consecutivos, independientemente de si intentos posteriores usan la contraseña correcta. El contador de intentos fallidos DEBE resetearse automáticamente a 0 en cuanto expiran los 15 minutos de bloqueo, sin requerir un login correcto previo.
- **FR-008**: El sistema DEBE mostrar en la página de bienvenida el nombre real del usuario autenticado.
- **FR-009**: El sistema DEBE permitir cerrar sesión desde la página de bienvenida.
- **FR-010**: El sistema DEBE tratar username y email como campos únicos entre todos los usuarios, con comparación insensible a mayúsculas/minúsculas.
- **FR-011**: El sistema NO DEBE ofrecer registro de nuevos usuarios, recuperación de contraseña ni gestión de hogares en esta feature — el usuario de prueba se crea mediante seed/migración fuera del flujo de la aplicación.
- **FR-012**: El sistema DEBE persistir un registro de auditoría de cada intento de login (usuario, resultado — éxito, fallo o bloqueado —, y marca de tiempo), independiente del contador de intentos fallidos usado para el bloqueo de FR-007. Los registros de auditoría DEBEN conservarse durante 90 días y purgarse pasado ese plazo.

### Key Entities *(include if feature involves data)*

- **Usuario**: representa a una persona con acceso a la plataforma. Incluye identificador único de login (username), email único, hash de contraseña, nombre real, apellidos, fecha de nacimiento (opcional), nivel de permisos dentro de su hogar, y una relación opcional con un Hogar. Puede existir sin hogar asociado.
- **Hogar**: representa una unidad familiar/doméstica a la que pueden pertenecer varios Usuarios. No se gestiona (crear/asociar) en esta feature, pero el modelo de datos debe soportar la relación desde ya.
- **Intento de login fallido / bloqueo**: estado asociado a un Usuario que registra intentos fallidos consecutivos y, en su caso, la marca de tiempo hasta la que el login está bloqueado.
- **Evento de login (auditoría)**: registro histórico independiente del contador de bloqueo, que guarda cada intento de login de un Usuario con su resultado (éxito, fallo o bloqueado) y su marca de tiempo, con fines de auditoría de seguridad. Se conserva 90 días y se purga pasado ese plazo.

> Nota de trazabilidad: el borrador `.specify/memory/db_ideas_001.md` (tablas `Usuarios`, `Hogares`, `Claves`) es el punto de partida para `/speckit.plan`, donde `db-designer` debe revisarlo contra `.claude/context/04_base_datos.md` (naming en inglés/plural, tamaño de campo de contraseña insuficiente para un hash, tabla de claves/catálogo, campos de auditoría, etc.) antes de incorporarlo al modelo de datos canónico.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un usuario con credenciales correctas completa el login y ve la página de bienvenida en menos de 3 segundos en condiciones normales, medidos desde el envío del formulario de login hasta el renderizado completo de la página de bienvenida.
- **SC-002**: El 100% de los intentos de login con credenciales incorrectas son rechazados sin crear sesión ni revelar si el usuario existe, tanto por el contenido de la respuesta como por su tiempo de respuesta (mitigación de enumeración por timing, ADR-0004) — con la única excepción, ya aceptada explícitamente, de que un intento contra un usuario actualmente bloqueado (FR-007) sí es distinguible por tiempo de respuesta frente a "no existe"/"password incorrecta", al rechazarse intencionalmente rápido y sin verificar la contraseña (ver Edge Cases).
- **SC-003**: Tras 5 intentos fallidos consecutivos, el 100% de los intentos adicionales (incluso con contraseña correcta) son rechazados hasta que expiren los 15 minutos de bloqueo.
- **SC-004**: Un evaluador humano (UAT) puede verificar el flujo completo (login correcto → bienvenida → logout → acceso denegado sin sesión) siguiendo un guion de prueba, sin necesidad de conocer la implementación interna.
- **SC-005**: Ninguna contraseña es recuperable en texto plano a partir de lo almacenado en base de datos, ni siquiera con acceso directo a la tabla de usuarios.

## Assumptions

- Volumen esperado bajo (uso doméstico/familiar: decenas de usuarios, sin concurrencia significativa) — no se establecen requisitos de escalado horizontal para esta feature.
- El usuario de prueba para UAT se inserta directamente en base de datos (vía script/seed o migración de datos), no a través de un flujo de registro de la aplicación, que queda fuera de alcance.
- La duración de la cookie de sesión se fija en 24 horas de inactividad máxima (valor razonable por defecto para una app doméstica; puede ajustarse en el plan técnico sin impacto en esta spec).
- El campo `Nivel` (ADM/MEM/VIS) del usuario se almacena pero no se usa todavía para restringir ninguna funcionalidad — no hay contenido protegido por permisos en esta feature más allá de "sesión activa sí/no".
- El registro de nuevos usuarios, la recuperación de contraseña olvidada, la gestión de hogares (crear/asociarse) y la autenticación de doble factor quedan explícitamente fuera de alcance y se abordarán en features posteriores.
- El bloqueo anti-fuerza-bruta de FR-007 es únicamente por usuario; no incluye throttling por IP ni ninguna otra protección a nivel de red. Se considera suficiente para el volumen de uso esperado de esta feature y queda fuera de alcance para una feature de seguridad posterior si el riesgo lo justifica.
- HTTPS se asume como transporte en cualquier entorno con datos reales (staging/producción); no es responsabilidad de esta feature configurar el certificado, pero sí que la cookie de sesión se marque `Secure` cuando la petición entrante llegue por HTTPS (detección por esquema de la petición, no por variable de entorno separada) y siempre `HttpOnly`.
- La ventana de 24 horas de inactividad de la sesión (ver arriba) se desliza con cualquier request autenticado que llegue con una sesión válida, sin distinguir el tipo de acción realizada.
- Username y email se asumen compuestos por caracteres ASCII (sin requisito de soporte de comparación insensible a mayúsculas/minúsculas para caracteres Unicode/locale-dependientes); no hay ningún otro requisito de internacionalización en esta feature.
- El despliegue de esta feature se asume en una única instancia de servidor (sin balanceo de carga con sesión pegajosa ni caché distribuida): al vivir `user_sessions` exclusivamente en PostgreSQL, una sesión sobrevive igualmente a un reinicio del proceso servidor, sin necesidad de estado adicional en memoria.
