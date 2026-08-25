"""Endpoints de login/logout/bienvenida (contracts/login.md)."""

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from financial_health_app.auth.audit import record_login_attempt
from financial_health_app.auth.hashing import verify_password_timing_safe
from financial_health_app.auth.lockout import (
    check_lockout,
    register_failed_attempt,
    reset_lockout,
)
from financial_health_app.auth.session import (
    create_session,
    invalidate_session,
    validate_session,
)
from financial_health_app.db import get_db
from financial_health_app.main import templates
from financial_health_app.models.user import User

router = APIRouter()

_GENERIC_ERROR = "Usuario o contraseña incorrectos"
_SESSION_COOKIE = "session"


def _current_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        return None
    return validate_session(db, token)


@router.get("/login")
def login_form(request: Request, db: Session = Depends(get_db)) -> Response:
    if _current_user(request, db) is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
def login_submit(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    user = db.scalars(
        select(User).where(
            (func.lower(User.username) == identifier.lower())
            | (func.lower(User.email) == identifier.lower())
        )
    ).one_or_none()

    # Auto-reseteo: si el bloqueo ya expiró, resetear ANTES de continuar (spec
    # Clarifications 2026-08-24 — sin requerir password correcta en este intento).
    if user is not None and user.locked_until is not None and not check_lockout(user):
        reset_lockout(user)

    if user is not None and check_lockout(user):
        # Bloqueado: rechazar sin reintentar la verificación de contraseña
        # (Edge Case de spec.md).
        record_login_attempt(
            db, user_id=user.id, identifier=identifier, result="locked"
        )
        db.commit()
        return templates.TemplateResponse(
            request, "login.html", {"error": _GENERIC_ERROR}, status_code=401
        )

    if user is not None and verify_password_timing_safe(password, user.password_hash):
        reset_lockout(user)
        token = create_session(db, user.id)
        record_login_attempt(
            db, user_id=user.id, identifier=identifier, result="success"
        )
        db.commit()
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            _SESSION_COOKIE,
            token,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
        )
        return response

    if user is None:
        verify_password_timing_safe(password, None)
    else:
        register_failed_attempt(db, user)

    record_login_attempt(
        db, user_id=user.id if user else None, identifier=identifier, result="failure"
    )
    db.commit()
    return templates.TemplateResponse(
        request, "login.html", {"error": _GENERIC_ERROR}, status_code=401
    )


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    token = request.cookies.get(_SESSION_COOKIE)
    if token is None or validate_session(db, token) is None:
        return RedirectResponse("/login", status_code=303)
    invalidate_session(db, token)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(_SESSION_COOKIE)
    return response


@router.get("/")
def welcome(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request, "welcome.html", {"first_name": user.first_name}
    )
