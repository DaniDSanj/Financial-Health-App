"""Modelos SQLAlchemy — importar aquí registra todas las tablas en Base.metadata."""

from financial_health_app.models.household import Household
from financial_health_app.models.keys_catalog import KeysCatalog
from financial_health_app.models.login_audit_log import LoginAuditLog
from financial_health_app.models.user import User
from financial_health_app.models.user_session import UserSession

__all__ = [
    "Household",
    "KeysCatalog",
    "LoginAuditLog",
    "User",
    "UserSession",
]
