# Specification Quality Checklist: Registro de usuarios y gestión de hogares

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-25
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Las 3 preguntas planteadas durante `/speckit.specify` quedaron resueltas (registro abierto, unión
  a hogar existente por código de invitación de un solo uso, activación de cuenta inmediata sin
  verificación de email).
- La 1ª pasada de `/speckit.clarify` resolvió 5 ambigüedades adicionales (ver sección
  "Clarifications" de `spec.md`, sesión 2026-08-25): requisito mínimo de contraseña (8 caracteres,
  sin composición forzada), separación del flujo de registro y gestión de hogares, exclusión
  explícita de protección anti-abuso en el registro, caducidad de 24h del código de invitación, y
  formato del código (alfanumérico corto de 8 caracteres).
- La 2ª pasada de `/speckit.clarify` (misma sesión) resolvió 3 ambigüedades más, todas sobre el
  código de invitación introducido en la 1ª pasada: bloqueo tras 5 intentos fallidos (FR-013, mismo
  patrón que FR-007 de `001-login-skeleton`), almacenamiento hasheado (no en claro), y no-unicidad
  del nombre de hogar (FR-014). Con esto se completan las 2 pasadas mínimas exigidas por
  `@.claude/context/01_estilo_comportamiento.md` §2.
- Durante `/speckit.plan`, la revisión de `db-designer` detectó un hueco entre FR-012 (auditoría con
  "resultado" por evento) y el diseño inicial (solo altas/asociaciones exitosas). El humano decidió
  cerrarlo añadiendo **FR-015** (log de auditoría de intentos de código de invitación, simétrico a
  `login_audit_log` de 001, retención 90 días) — añadido directamente a `spec.md` para mantener la
  trazabilidad spec↔plan, sin necesitar una tercera pasada formal de `/speckit.clarify` porque no era
  una ambigüedad de la spec sino un hallazgo de diseño de esquema.
- Tras `/speckit.plan`, `/speckit.checklist` generó `checklists/general.md` (25 items, gate formal de
  calidad de requisitos) y los 25 quedaron resueltos el mismo día: precisión de FR-005/FR-006/
  FR-007/FR-011 (longitudes máximas, condición de nombre no vacío, mostrar código una sola vez,
  consistencia bajo uso simultáneo del código), 2 nuevos Edge Cases, y 6 bullets nuevos en
  Assumptions (límites de invitaciones/miembros, accesibilidad, auditoría de registro fallido,
  Unicode en nombre de hogar, y confirmación humana del modelo de despliegue — servidor
  local/ordenador personal, sin exposición pública en esta versión). Todos los items del checklist
  de calidad de spec siguen pasando.
- `/speckit.analyze` (2026-08-26) detectó 5 hallazgos menores de consistencia entre spec/plan/tasks/
  contratos, todos resueltos: límites máximos de FR-011 y validación de nombre de hogar añadidos a
  los contratos de registro/hogar (que solo mencionaban el caso más simple), opcionalidad de
  `last_name` documentada como Assumption, test positivo de FR-014 (nombres de hogar duplicados)
  añadido a T006, y la fila del Principio III en `plan.md` actualizada de pendiente a cumplida ahora
  que `tasks.md` ya refleja TDD estricto.
- El subagente `spec-critic` (2026-08-26), con contexto limpio y verificación cruzada contra el
  código real de `001-login-skeleton`, devolvió veredicto **GO condicionado** (sin violación de
  ningún principio MUST de la constitución) con 9 hallazgos no bloqueantes. 4 de ellos eran
  ambigüedades de diseño reales, resueltas con el humano (todas con la opción recomendada): FR-008
  ahora garantiza explícitamente la concurrencia en creación de hogar (con protección atómica +
  test dedicado); FR-011 restringe `username`/`email` a ASCII (el registro es abierto, a diferencia
  del alta controlada de 001); FR-015 aclara que el hogar es "identificable" en el log de auditoría
  incluso con un código ya usado/caducado; y `POST /register` captura `IntegrityError` y la traduce
  a `409` (con test de concurrencia dedicado) en vez de dejar una ventana de `500` no controlado. Los
  5 hallazgos restantes se resolvieron directamente por ser de bajo riesgo sin ambigüedad de negocio
  real: nota sobre `permission_level_code='MEM'` sin significado real añadida a Assumptions,
  corrección cosmética del Acceptance Scenario 3 de US1, y 2 hallazgos aceptados como deuda de
  gobernanza/lectura ya válida pre-existente desde `001-login-skeleton` sin requerir cambios (FR-012
  solo cubre auditoría de éxito, no de fallo; sin ADR dedicado para la convención de auditoría
  reducida en tablas de una sola transición de estado — mismo patrón ya aceptado para
  `user_sessions`).
- **UAT humana (2026-08-26)**, ejecutada por el usuario siguiendo `quickstart.md`: los 5 escenarios
  pasaron sin fallos funcionales. Dos observaciones registradas, ambas resueltas o documentadas:
  - Mensaje de error del registro demasiado genérico (no indicaba qué campo falló) — **resuelto**:
    `routers/register.py` → `_validate()` ahora devuelve un mensaje específico por regla de FR-011,
    con test de regresión (`test_different_validation_failures_produce_different_messages`).
  - Redundancia de `users.permission_level_group` (siempre `'NUS'`) — **backlog, fuera de alcance de
    002**: la columna es heredada de `001-login-skeleton`, no introducida por esta feature. Dirección
    de solución señalada por el humano: el dato de a qué grupo pertenece `permission_level_code` debe
    vivir en los metadatos del propio campo `permission_level_code` de `users` (constraint/comment de
    esquema fijando el grupo `NUS`), no como columna de fila redundante ni movido a `keys_catalog`.
    Requiere el protocolo de cambio de esquema completo sobre una tabla que ya usa `001` — candidato a
    ADR/feature propia.
  - Escenario 2, paso 4 (rechazo de segundo hogar) no verificable vía UI por diseño — aceptado el test
    automatizado como evidencia suficiente (ver nota añadida a `quickstart.md`).
