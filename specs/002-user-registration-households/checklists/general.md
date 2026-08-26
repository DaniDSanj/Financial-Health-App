# General Requirements Quality Checklist: Registro de usuarios y gestión de hogares

**Purpose**: Gate formal de calidad de requisitos antes de `/speckit.tasks` — validar que `spec.md`
está completo, claro, consistente y medible, no verificar que la implementación funcione.
**Created**: 2026-08-26
**Feature**: [spec.md](../spec.md)

**Note**: Generado por `/speckit-checklist`. Cada item evalúa la REDACCIÓN de los requisitos, no el
comportamiento del sistema. Resuelto íntegramente el 2026-08-26 — cada item lleva su resolución
inline.

## Requirement Completeness

- [x] CHK001 - Is a maximum length specified for the household name field? [Gap, Spec §FR-005]
      *Resuelto: FR-005 ahora fija 100 caracteres (mismo tamaño que la columna `name` de
      `households` en `data-model.md`).*
- [x] CHK002 - Are limits on the number of concurrently active invitation codes per household
      specified? [Gap, Edge Case, Spec §FR-007]
      *Resuelto: sin límite, por decisión — nuevo bullet en Assumptions (mismo criterio que la
      ausencia de anti-abuso ya aceptada en FR-004/FR-013).*
- [x] CHK003 - Is a maximum household member count specified? [Gap]
      *Resuelto: sin límite, por decisión — mismo bullet de Assumptions que CHK002.*
- [x] CHK004 - Are accessibility requirements defined for the registration and household forms?
      [Gap, Non-Functional]
      *Resuelto: fuera de alcance, documentado explícitamente en Assumptions — mismo precedente que
      `001-login-skeleton` (ningún estándar de accesibilidad fijado todavía en el proyecto).*
- [x] CHK005 - Is the constraint that a generated invitation code is shown only once stated as a
      functional requirement? [Gap, Traceability, Spec §FR-007]
      *Resuelto: añadido explícitamente a FR-007.*

## Requirement Clarity

- [x] CHK006 - Is "formato de email válido" (FR-011) specified precisely enough to be objectively
      testable? [Clarity, Spec §FR-011]
      *Resuelto: FR-011 ahora especifica "sintaxis `usuario@dominio` válida, sin verificar que el
      buzón exista realmente".*
- [x] CHK007 - Is the password rule "alineado con NIST 800-63B" (FR-011) self-contained? [Clarity,
      Spec §FR-011]
      *Revisado, sin cambio: la regla ya estaba completa en el propio FR-011 (≥8 caracteres, sin
      composición forzada) — la referencia a NIST 800-63B es contexto de apoyo, no información
      necesaria para aplicar la regla. Aprovechado para añadir también el máximo (128).*
- [x] CHK008 - Is "nombre" for a household defined with any format constraint? [Clarity, Spec
      §FR-005]
      *Resuelto junto con CHK001/CHK016: FR-005 ahora rechaza nombre vacío o solo espacios.*

## Requirement Consistency

- [x] CHK009 - Are the permission-level assignment rules (ADM/MEM) consistent between FR y Key
      Entities/Assumptions? [Consistency, Spec §FR-005/FR-006]
      *Revisado, sin cambio: FR-005/FR-006, Key Entities ("Nivel de permisos") y Assumptions ya
      coinciden exactamente (ADM al crear, MEM al asociarse) — no había inconsistencia real.*
- [x] CHK010 - Is the "separado, no obligatorio" household step consistently reflected in every
      User Story? [Consistency]
      *Revisado, sin cambio: US1 no menciona hogar; US2/US3 parten explícitamente de "usuario ya
      autenticado que todavía no pertenece a ningún hogar" — consistente en las tres historias.*

## Acceptance Criteria Quality

- [x] CHK011 - Can SC-005 be objectively pass/failed? [Measurability, Spec §SC-005]
      *Revisado, sin cambio: mismo patrón textual que SC-004 de `001-login-skeleton` (ya aceptado
      como criterio de UAT humana, no automatizable por diseño — ver
      `01_estilo_comportamiento.md` §3, UAT explícita para flujos user-facing).*
- [x] CHK012 - Are "condiciones normales" (SC-001/003/004) defined? [Clarity, Spec §SC-001]
      *Revisado, sin cambio: mismo término ya usado sin más definición en SC-001 de
      `001-login-skeleton` (precedente aceptado del proyecto, no específico de esta feature).*

## Scenario Coverage

- [x] CHK013 - Are requirements defined for concurrent use of the same invitation code by two
      users? [Coverage, Gap]
      *Resuelto: FR-006 ahora exige explícitamente que como máximo un usuario consiga asociarse en
      caso de introducción simultánea del mismo código.*
- [x] CHK014 - Are requirements defined for zero active invitation codes? [Coverage, Gap]
      *Resuelto: nuevo bullet en Edge Cases — no es un estado especial, el formulario de generación
      siempre está disponible.*
- [x] CHK015 - Are requirements defined for a user who never creates/joins a household? [Coverage,
      Spec §Assumptions]
      *Revisado, sin cambio: ya cubierto por el bullet de Assumptions "seguir sin tener hogar
      asociado... sigue siendo un estado válido".*

## Edge Case Coverage

- [x] CHK016 - Is behavior specified for a whitespace-only household name? [Edge Case, Gap]
      *Resuelto junto con CHK001/CHK008 en FR-005.*
- [x] CHK017 - Is behavior specified for excessively long input in the relevant fields? [Edge Case,
      Gap]
      *Resuelto: FR-011 ahora fija máximo de contraseña (128) y remite a los límites ya existentes
      de `username`/`email`/`first_name`/`last_name` (50/255/100/50, heredados de
      `001-login-skeleton`); FR-005 fija 100 para nombre de hogar. Todos rechazan con error de
      validación, sin truncar en silencio.*
- [x] CHK018 - Is repeated resubmission of a duplicate email/username addressed? [Edge Case, Spec
      §FR-002]
      *Revisado, sin cambio: ya cubierto por el bullet de Assumptions sobre ausencia de protección
      anti-abuso en el registro (FR-004) — el mismo criterio aplica a reintentos repetidos de
      duplicados, no es una laguna nueva.*

## Non-Functional Requirements

- [x] CHK019 - Is the invitation code's character set captured as a functional requirement, or only
      in supporting documents? [Traceability, Spec §Clarifications]
      *Revisado, sin cambio: se deja deliberadamente a nivel de plan/research — es un detalle de
      implementación (qué alfabeto exacto usa `generate_code()`) que no cambia el comportamiento
      observable por el usuario ("código alfanumérico de 8 caracteres", ya en FR-007); elevarlo a
      FR sería sobre-especificar la spec con un detalle de UX de bajo impacto.*
- [x] CHK020 - Are logging requirements for failed registration attempts specified? [Gap,
      Non-Functional]
      *Resuelto: nuevo bullet en Assumptions explicando por qué NO se auditan (sin señal de
      seguridad equivalente a login/código de invitación) — decisión explícita, no laguna.*
- [x] CHK021 - Are character-set/localization assumptions for the household name documented? [Gap,
      Assumption]
      *Resuelto: nuevo bullet en Assumptions — nombre de hogar acepta Unicode libremente, a
      diferencia de username/email.*

## Dependencies & Assumptions

- [x] CHK022 - Is the "not publicly reachable" deployment assumption validated? [Assumption, Spec
      §Assumptions]
      *Resuelto — confirmado con el humano: la primera versión se mantiene en un servidor
      local/ordenador personal, sin exposición pública. Assumption reescrita para reflejarlo de
      forma concreta en vez de genérica ("red doméstica/VPN, o un control de acceso...").*
- [x] CHK023 - Is the dependency on `001-login-skeleton`'s session/hashing mechanisms traceable to
      specific files? [Traceability, Spec §Assumptions]
      *Revisado, sin cambio: la spec referencia el directorio (`src/financial_health_app/auth/`),
      nivel de detalle apropiado para un documento de negocio — la trazabilidad a funciones
      concretas (`create_session()`, `hash_password()`) ya vive en `plan.md`/`research.md`, que es
      donde corresponde.*

## Ambiguities & Conflicts

- [x] CHK024 - Is there ambiguity about whether `VIS` could be assigned by a future extension?
      [Ambiguity, Spec §Key Entities]
      *Revisado, sin cambio: Key Entities ya dice explícitamente "queda reservado para uso futuro"
      — sin ambigüedad real.*
- [x] CHK025 - Is there unresolved tension between FR-004 (open registration) and the public
      exposure caveat? [Ambiguity, Spec §Assumptions]
      *Resuelto junto con CHK022: la assumption reescrita deja claro que, si cambia el modelo de
      despliegue, el registro abierto es "un riesgo a revisar en una feature de seguridad
      posterior" — no requiere un campo de "responsable" adicional en la spec.*

## Notes

- Check items off as completed: `[x]`
- Todos los items resueltos el 2026-08-26, misma sesión que su generación — ver los bullets nuevos/
  editados en `spec.md` (FR-005, FR-006, FR-007, FR-011, Edge Cases, Assumptions) para el detalle.
- 25/25 items, ≥80% con marcador `Spec §...`/`[Gap]`/`[Ambiguity]`/`[Assumption]`/`[Coverage]`.
