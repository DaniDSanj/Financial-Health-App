# Data Model: 001-login-skeleton

> Reflejo local, orientado a implementación, del modelo canónico en
> `.specify/memory/data-model.md` (entidades introducidas en esta feature: `keys_catalog`,
> `households`, `users`, `user_sessions`, `login_audit_log`). Ante cualquier discrepancia, el
> canónico es la fuente de verdad — este fichero se actualiza para reflejarlo, nunca al revés.
>
> Esquema diseñado y aprobado vía `db-designer` siguiendo `.claude/context/04_base_datos.md`, a
> partir del borrador humano `.specify/memory/db_ideas_001.md` (tablas `Usuarios`/`Hogares`/`Claves`).

## Diagrama

```mermaid
erDiagram
    HOUSEHOLDS ||--o{ USERS : "tiene"
    USERS ||--o| USER_SESSIONS : "tiene (0..1)"
    USERS ||--o{ LOGIN_AUDIT_LOG : "genera"
    KEYS_CATALOG ||--o{ USERS : "clasifica (permission_level)"

    HOUSEHOLDS {
        SERIAL id PK
        VARCHAR_100 name
        TIMESTAMPTZ created_at
        INTEGER created_by FK
        TIMESTAMPTZ updated_at
        INTEGER updated_by FK
        INTEGER version
    }

    USERS {
        SERIAL id PK
        VARCHAR_50 username UK
        VARCHAR_255 email UK
        VARCHAR_255 password_hash
        VARCHAR_100 first_name
        VARCHAR_50 last_name
        DATE birth_date
        INTEGER household_id FK
        CHAR_3 permission_level_group FK
        CHAR_3 permission_level_code FK
        INTEGER failed_login_attempts
        TIMESTAMPTZ locked_until
        TIMESTAMPTZ created_at
        INTEGER created_by FK
        TIMESTAMPTZ updated_at
        INTEGER updated_by FK
        INTEGER version
    }

    USER_SESSIONS {
        INTEGER user_id PK_FK
        VARCHAR_255 session_token UK
        TIMESTAMPTZ expires_at
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    LOGIN_AUDIT_LOG {
        BIGSERIAL id PK
        INTEGER user_id FK
        VARCHAR_255 attempted_identifier
        VARCHAR_20 result
        TIMESTAMPTZ occurred_at
    }

    KEYS_CATALOG {
        SERIAL id PK
        CHAR_3 group_code UK
        INTEGER sort_order
        BOOLEAN is_header
        CHAR_3 code UK
        VARCHAR_100 description
        TIMESTAMPTZ created_at
        INTEGER created_by FK
        TIMESTAMPTZ updated_at
        INTEGER updated_by FK
        INTEGER version
    }
```

## Entidades

### `keys_catalog`

Catálogo genérico transversal (ex `Claves` del borrador humano). Permite añadir valores de dominio
sin migración de esquema. Único dominio poblado en esta feature: grupo `NUS` (niveles de usuario).

| Columna | Tipo | Constraints | Notas |
|---|---|---|---|
| id | SERIAL | PK | |
| group_code | CHAR(3) | NOT NULL | p. ej. `NUS` |
| sort_order | INTEGER | NOT NULL | orden visual dentro del grupo |
| is_header | BOOLEAN | NOT NULL DEFAULT FALSE | TRUE solo en la fila de cabecera del grupo |
| code | CHAR(3) | NULL | NULL únicamente en la fila de cabecera |
| description | VARCHAR(100) | NOT NULL | descripción de negocio legible |
| created_at / created_by / updated_at / updated_by / version | — | auditoría estándar completa | |

- `UNIQUE (group_code, code)` — soporta la FK compuesta desde `users` y la query de resolución de
  descripción.
- Índice `group_code` — listar/ordenar los valores de un grupo.
- **Seed obligatorio antes de crear cualquier usuario** (grupo `NUS`):

  | group_code | sort_order | is_header | code | description |
  |---|---|---|---|---|
  | NUS | 0 | TRUE | NULL | Niveles de usuario |
  | NUS | 1 | FALSE | ADM | Administrador (todos los permisos) |
  | NUS | 2 | FALSE | MEM | Miembro (ver y editar, no borrar) |
  | NUS | 3 | FALSE | VIS | Visor (solo lectura) |

### `households`

Unidad familiar/doméstica. Sin gestión propia (crear/asociar) en esta feature — existe solo para
soportar la FK nullable desde `users`.

| Columna | Tipo | Constraints |
|---|---|---|
| id | SERIAL | PK |
| name | VARCHAR(100) | NOT NULL |
| created_at / created_by / updated_at / updated_by / version | — | auditoría estándar completa |

### `users`

| Columna | Tipo | Constraints | Notas |
|---|---|---|---|
| id | SERIAL | PK | |
| username | VARCHAR(50) | NOT NULL, único (índice funcional `LOWER(username)`) | FR-002, FR-010 |
| email | VARCHAR(255) | NOT NULL, único (índice funcional `LOWER(email)`) | FR-002, FR-010 |
| password_hash | VARCHAR(255) | NOT NULL | Argon2id, ver `research.md` §2 |
| first_name | VARCHAR(100) | NOT NULL | |
| last_name | VARCHAR(50) | NULL | |
| birth_date | DATE | NULL | |
| household_id | INTEGER | NULL, FK → `households(id)` | sin gestión en esta feature |
| permission_level_group | CHAR(3) | NOT NULL DEFAULT 'NUS' | |
| permission_level_code | CHAR(3) | NOT NULL | FK compuesta junto al anterior → `keys_catalog(group_code, code)` |
| failed_login_attempts | INTEGER | NOT NULL DEFAULT 0 | FR-007 |
| locked_until | TIMESTAMPTZ | NULL | FR-007; NULL = sin bloqueo activo |
| created_at / created_by / updated_at / updated_by / version | — | auditoría estándar completa (`created_by`/`updated_by` autorreferencian `users`) |

**Reglas de negocio relevantes** (implementadas en `auth/lockout.py`, no en el esquema):
- Al fallar un login: `failed_login_attempts += 1`; si llega a 5, fijar `locked_until = now() + 15min`.
- Al expirar `locked_until` (es decir, `locked_until < now()`): resetear `failed_login_attempts = 0`
  automáticamente en el siguiente intento, sin requerir un login correcto (spec → Clarifications).
- Al hacer login correcto: `failed_login_attempts = 0`, `locked_until = NULL`.

### `user_sessions`

Sesión de servidor única por usuario. PK = `user_id` (desviación deliberada del default `id`): un
nuevo login hace `UPSERT` sobre la fila existente, invalidando de forma nativa cualquier sesión
anterior (FR-004) sin lógica adicional.

| Columna | Tipo | Constraints |
|---|---|---|
| user_id | INTEGER | PK, FK → `users(id)` ON DELETE CASCADE |
| session_token | VARCHAR(255) | NOT NULL, UNIQUE |
| expires_at | TIMESTAMPTZ | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

Sin `created_by`/`updated_by` (actor = `user_id`, ya PK) ni `version` (fila reemplazada por completo
en cada login) — desviación documentada y justificada en el canónico.

### `login_audit_log`

Append-only. Un evento por cada intento de login (éxito, fallo o bloqueado), independiente del
contador de `users`. Retención: 90 días (purga vía job de mantenimiento, fuera del alcance de código
de aplicación de esta feature — ver Tareas de implementación).

| Columna | Tipo | Constraints | Notas |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| user_id | INTEGER | NULL, FK → `users(id)` | NULL si `attempted_identifier` no existe |
| attempted_identifier | VARCHAR(255) | NOT NULL | username o email tal como se introdujo |
| result | VARCHAR(20) | NOT NULL, CHECK IN ('success','failure','locked') | |
| occurred_at | TIMESTAMPTZ | NOT NULL DEFAULT now() | índice BRIN (dato secuencial de log) |

Sin `created_by` (el intento a menudo no está autenticado).

## Orden de creación (migración Alembic)

Por las FKs cruzadas de auditoría (`keys_catalog.created_by`/`households.created_by` → `users`,
`users.household_id` → `households`, `users.permission_level_*` → `keys_catalog`):

1. `keys_catalog` y `households` (columnas `created_by`/`updated_by` nullable, sin FK todavía).
2. `users` (ya puede declarar sus FKs hacia `households` y `keys_catalog`, que existen).
3. `user_sessions`, `login_audit_log` (dependen solo de `users`).
4. `ALTER TABLE` para añadir `keys_catalog.created_by/updated_by` y
   `households.created_by/updated_by` → `users(id)`, una vez que `users` ya existe.
5. Seed del grupo `NUS` en `keys_catalog` (con `created_by`/`updated_by` en `NULL` — primera fila del
   sistema, sin usuario válido todavía al que atribuirla).
