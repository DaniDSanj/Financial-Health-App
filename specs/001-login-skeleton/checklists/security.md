# Security/Auth Requirements Quality Checklist: Esqueleto de login y modelo de datos base

**Purpose**: Validar la calidad (completitud, claridad, consistencia, medibilidad) de los requisitos
de seguridad/autenticación de `spec.md`, como gate previo a `/speckit-tasks`. Este checklist evalúa
la especificación, no la implementación.
**Created**: 2026-08-24
**Feature**: [spec.md](../spec.md)

## Requirement Completeness

- [x] CHK001 - ¿Está especificado cómo se genera/hashea la contraseña del usuario semilla fuera del flujo de la aplicación? [Gap, Spec §Assumptions] — Diferido a `/speckit-tasks`: ya cubierto operativamente por el ejemplo SQL de `quickstart.md`; es un paso de seed, no un requisito funcional de la app.
- [x] CHK002 - ¿Están definidos los requisitos sobre qué ocurre con una sesión activa si el usuario correspondiente se elimina? [Gap] — Sin cambio: el borrado de usuarios está fuera de alcance de esta feature (FR-011), el caso es N/A.
- [x] CHK003 - ¿Están definidos los requisitos de comportamiento ante intentos fallidos concurrentes/casi simultáneos sobre el mismo usuario (incremento del contador)? [Gap, Edge Case] — Diferido a `/speckit-tasks`: mecanismo de concurrencia (lock/transacción a nivel de fila) es detalle de `auth/lockout.py`, no de la spec.
- [x] CHK004 - ¿Está especificada la frecuencia/mecanismo de ejecución del job de purga de auditoría a 90 días? [Gap, Spec §FR-012] — Diferido a `/speckit-tasks`: decisión operativa (cron/Alembic/script); FR-012 ya fija la política de retención.
- [x] CHK005 - ¿Están definidos los requisitos ante un fallo o retraso del job de purga de auditoría? [Gap] — Diferido a `/speckit-tasks`: no bloqueante, a resolver junto con CHK004.

## Requirement Clarity

- [x] CHK006 - ¿La condición "cuando el entorno lo permita" (cookie `Secure`/`HttpOnly`) está cuantificada con un criterio concreto y verificable? [Ambiguity, Spec §Assumptions] — Resuelto vía `/speckit.clarify` (2026-08-25): Secure se activa si la petición llega por HTTPS (detección por esquema de la petición).
- [x] CHK007 - ¿Está definido qué cuenta como "actividad" a efectos de la ventana deslizante de 24h de la sesión? [Clarity, Gap] — Resuelto vía `/speckit.clarify` (2026-08-25): cualquier request autenticado desliza `expires_at`.
- [x] CHK008 - ¿SC-001 especifica el punto de inicio y fin exactos de la medición de "menos de 3 segundos"? [Clarity, Spec §SC-001] — Resuelto por edición directa: medición desde el envío del formulario hasta el renderizado completo de la página de bienvenida.
- [x] CHK009 - ¿La comparación insensible a mayúsculas/minúsculas de FR-010 especifica si aplica solo a ASCII o también a caracteres Unicode/locale-dependientes? [Ambiguity, Spec §FR-010] — Resuelto por edición directa: username/email se asumen ASCII-only, añadido a Assumptions.

## Requirement Consistency

- [x] CHK010 - ¿FR-007 y FR-012 dejan claro, sin ambigüedad, qué valor de `result` se audita cuando el intento se rechaza únicamente por bloqueo activo (sin llegar a verificar la contraseña)? [Consistency, Spec §FR-007, Spec §FR-012] — Sin cambio: FR-012 ya define explícitamente tres resultados auditables (éxito/fallo/bloqueado); falso positivo del checklist inicial.
- [x] CHK011 - ¿Es consistente el requisito de mensaje de error genérico (FR-006) con el hecho de que el registro de auditoría (FR-012) sí puede distinguir internamente causas que el usuario nunca ve? [Consistency, Spec §FR-006, Spec §FR-012] — Sin cambio: comportamiento de seguridad deseado (no revelar internals al usuario), no una inconsistencia.

## Acceptance Criteria Quality

- [x] CHK012 - ¿Puede verificarse SC-005 objetivamente sin prescribir una implementación de hashing concreta? [Measurability, Spec §SC-005] — Sin cambio: ya redactado sin prescribir algoritmo.
- [x] CHK013 - ¿Es SC-003 verificable de forma determinista en el caso límite del intento número 5 frente al 6? [Measurability, Spec §SC-003] — Sin cambio: FR-007/SC-003 ya son deterministas (5º intento activa el bloqueo, 6º en adelante se rechaza por bloqueo).

## Scenario Coverage / Edge Case Coverage

- [x] CHK014 - ¿Existe requisito sobre si el usuario recibe algún aviso de que su sesión anterior fue invalidada por un login desde otro dispositivo? [Gap, Coverage] — Resuelto vía `/speckit.clarify` (2026-08-25): invalidación silenciosa, sin aviso específico (FR-004).
- [x] CHK015 - ¿Está especificado el comportamiento de una sesión ya emitida frente a un reinicio del servidor? [Gap] — Resuelto por edición directa: `user_sessions` persiste en PostgreSQL (no en memoria), sobrevive a un reinicio por diseño; añadido a Assumptions.
- [x] CHK016 - ¿Está definido qué debe ver el usuario ante un fallo de base de datos durante el proceso de login? [Gap, Exception Flow] — Diferido a `/speckit-tasks`: manejo de errores estándar (página de error genérica), no requiere un FR nuevo.

## Dependencies & Assumptions

- [x] CHK017 - ¿Está la decisión de sesión única (FR-004) reflejada de forma trazable y sin contradicciones entre `spec.md`, `research.md` y `ADR-0002`? [Traceability] — Sin cambio: verificado consistente entre los tres documentos.
- [x] CHK018 - ¿Está documentada explícitamente la asunción de despliegue en instancia única (sin sesión pegajosa/caché distribuida), dado que `user_sessions` vive solo en PostgreSQL? [Assumption, Spec §Assumptions] — Resuelto por edición directa: añadido a Assumptions.

## Ambiguities & Conflicts

- [x] CHK019 - ¿Se especifica si el formulario de login debe deshabilitar el autocompletado/autofill de contraseña, o queda explícitamente fuera de alcance? [Gap] — Diferido a `/speckit-tasks`: detalle de la plantilla `login.html`, sin impacto en ningún FR/SC existente.

## Notes

- Ítems marcados `[Gap]` señalan ausencia de requisito, no un fallo de implementación — resolverlos
  antes de `/speckit-tasks` evita que el detalle se decida de forma implícita durante el desarrollo.
- Ítems marcados `[Ambiguity]`/`[Consistency]` requieren aclarar o reconciliar texto ya existente en
  `spec.md`, posiblemente vía una tercera pasada dirigida de `/speckit.clarify` sobre estos puntos
  concretos, o edición directa de la spec si la respuesta es obvia.
- CHK017 es el único ítem de verificación cruzada entre documentos (no solo `spec.md`); se incluye
  porque la trazabilidad entre spec/plan/ADR es explícitamente una preocupación del ciclo SDD de este
  proyecto (`02_documentacion_mantenibilidad.md`).
- **Cierre (2026-08-25)**: 19/19 ítems cerrados. 3 resueltos vía tercera pasada dirigida de
  `/speckit.clarify` (CHK006, CHK007, CHK014); 4 resueltos por edición directa de `spec.md` sin
  necesitar decisión del humano (CHK008, CHK009, CHK015, CHK018); 5 confirmados como ya resueltos por
  el propio texto de la spec, sin cambios (CHK010, CHK011, CHK012, CHK013, CHK017); 7 diferidos
  explícitamente a `/speckit-tasks` por ser detalle de implementación, no de requisitos (CHK001,
  CHK002, CHK003, CHK004, CHK005, CHK016, CHK019). Gate previo a `/speckit-tasks` superado.
