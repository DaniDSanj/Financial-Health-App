"""Script de purga: borra filas de household_invitation_attempts_log con más de
90 días.

FR-015. Uso: uv run python scripts/purge_household_invitation_attempts_log.py

Mismo patrón que scripts/purge_login_audit_log.py de 001 — la programación
periódica (cron, tarea programada, etc.) es un paso operativo fuera del alcance
de esta feature.
"""

from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import CursorResult, delete
from sqlalchemy.orm import Session

from financial_health_app.db import SessionLocal
from financial_health_app.models.household_invitation_attempt_log import (
    HouseholdInvitationAttemptLog,
)

_RETENTION = timedelta(days=90)


def purge_household_invitation_attempts_log(
    db: Session, *, now: datetime | None = None
) -> int:
    """Borra las filas con occurred_at anterior al umbral de retención. No hace
    commit."""
    cutoff = (now or datetime.now(UTC)) - _RETENTION
    result = cast(
        CursorResult,
        db.execute(
            delete(HouseholdInvitationAttemptLog).where(
                HouseholdInvitationAttemptLog.occurred_at < cutoff
            )
        ),
    )
    return result.rowcount


def main() -> None:
    db = SessionLocal()
    try:
        deleted = purge_household_invitation_attempts_log(db)
        db.commit()
        print(f"Filas purgadas de household_invitation_attempts_log: {deleted}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
