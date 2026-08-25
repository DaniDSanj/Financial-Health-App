"""Script de purga: borra filas de login_audit_log con más de 90 días.

FR-012, CHK004/CHK005. Uso: uv run python scripts/purge_login_audit_log.py

La programación periódica (cron, tarea programada de Windows, etc.) es un paso
operativo fuera del alcance de esta feature — este script solo implementa el
borrado en sí; quien despliegue la app decide cómo y cuándo invocarlo
repetidamente.
"""

from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import CursorResult, delete
from sqlalchemy.orm import Session

from financial_health_app.db import SessionLocal
from financial_health_app.models.login_audit_log import LoginAuditLog

_RETENTION = timedelta(days=90)


def purge_login_audit_log(db: Session, *, now: datetime | None = None) -> int:
    """Borra las filas con occurred_at anterior al umbral de retención. No hace
    commit."""
    cutoff = (now or datetime.now(UTC)) - _RETENTION
    result = cast(
        CursorResult,
        db.execute(delete(LoginAuditLog).where(LoginAuditLog.occurred_at < cutoff)),
    )
    return result.rowcount


def main() -> None:
    db = SessionLocal()
    try:
        deleted = purge_login_audit_log(db)
        db.commit()
        print(f"Filas purgadas de login_audit_log: {deleted}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
