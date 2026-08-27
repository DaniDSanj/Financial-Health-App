"""Endpoint de registro de usuario (contracts/register.md)."""

import re

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from financial_health_app.auth.hashing import hash_password
from financial_health_app.auth.session import create_session, validate_session
from financial_health_app.db import get_db
from financial_health_app.models.user import User
from financial_health_app.templating import templates

router = APIRouter()

_SESSION_COOKIE = "session"
_DUPLICATE_ERROR = "Ese usuario o email ya está en uso"
_PASSWORD_LENGTH_ERROR = "La contraseña debe tener entre 8 y 128 caracteres"
_USERNAME_LENGTH_ERROR = "El usuario no puede superar los 50 caracteres"
_USERNAME_ASCII_ERROR = "El usuario solo puede contener caracteres ASCII"
_EMAIL_LENGTH_ERROR = "El email no puede superar los 255 caracteres"
_EMAIL_ASCII_ERROR = "El email solo puede contener caracteres ASCII"
_EMAIL_SYNTAX_ERROR = "El email no tiene un formato válido"
_FIRST_NAME_LENGTH_ERROR = "El nombre no puede superar los 100 caracteres"
_LAST_NAME_LENGTH_ERROR = "Los apellidos no pueden superar los 50 caracteres"
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _current_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        return None
    return validate_session(db, token)


def _validate(
    *,
    first_name: str,
    last_name: str | None,
    username: str,
    email: str,
    password: str,
) -> str | None:
    """Valida los campos del formulario (FR-011). Devuelve un mensaje de error
    específico según qué regla falló (UAT 2026-08-26: un mensaje genérico no le
    dice al usuario qué corregir), o None si todo es válido."""
    if not (8 <= len(password) <= 128):
        return _PASSWORD_LENGTH_ERROR
    if len(username) > 50:
        return _USERNAME_LENGTH_ERROR
    if not username.isascii():
        return _USERNAME_ASCII_ERROR
    if len(email) > 255:
        return _EMAIL_LENGTH_ERROR
    if not email.isascii():
        return _EMAIL_ASCII_ERROR
    if not _EMAIL_RE.match(email):
        return _EMAIL_SYNTAX_ERROR
    if len(first_name) > 100:
        return _FIRST_NAME_LENGTH_ERROR
    if last_name is not None and len(last_name) > 50:
        return _LAST_NAME_LENGTH_ERROR
    return None


def _find_conflicting_user(db: Session, *, username: str, email: str) -> User | None:
    return db.scalars(
        select(User).where(
            (func.lower(User.username) == username.lower())
            | (func.lower(User.email) == email.lower())
        )
    ).one_or_none()


def register_user(
    db: Session,
    *,
    username: str,
    email: str,
    password_hash: str,
    first_name: str,
    last_name: str | None,
) -> User | None:
    """Crea el usuario. No hace commit — el llamador controla la transacción.

    Devuelve None si username/email ya está en uso — detectado por la
    comprobación previa (caso común) o por `IntegrityError` al forzar el flush
    (cierra la ventana de carrera entre dos registros simultáneos con el mismo
    valor, ver spec-critic hallazgo 4).
    """
    existing = _find_conflicting_user(db, username=username, email=email)
    if existing is not None:
        return None
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        first_name=first_name,
        last_name=last_name,
        permission_level_code="MEM",
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return None
    return user


@router.get("/register")
def register_form(request: Request, db: Session = Depends(get_db)) -> Response:
    if _current_user(request, db) is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "register.html", {})


@router.post("/register")
def register_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str | None = Form(None),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    error = _validate(
        first_name=first_name,
        last_name=last_name,
        username=username,
        email=email,
        password=password,
    )
    if error:
        return templates.TemplateResponse(
            request, "register.html", {"error": error}, status_code=422
        )

    user = register_user(
        db,
        username=username,
        email=email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
    )
    if user is None:
        # register_user() ya deshizo cualquier cambio pendiente (o no llegó a
        # añadir nada) — no volver a llamar a db.rollback() aquí: sobre la sesión
        # compartida por request de los tests (fixture db_session) un rollback sin
        # nada pendiente deshace también el commit ya confirmado de una petición
        # anterior en el mismo test.
        return templates.TemplateResponse(
            request, "register.html", {"error": _DUPLICATE_ERROR}, status_code=409
        )

    token = create_session(db, user.id)
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
