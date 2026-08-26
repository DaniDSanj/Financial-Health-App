"""Endpoints de gestión de hogar (contracts/household.md)."""

from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import CursorResult, select, update
from sqlalchemy.orm import Session

from financial_health_app.auth.invite_audit import record_invite_attempt
from financial_health_app.auth.invite_code import generate_code, hash_code
from financial_health_app.auth.invite_lockout import (
    check_invite_lockout,
    register_failed_invite_attempt,
    reset_invite_lockout,
)
from financial_health_app.auth.session import validate_session
from financial_health_app.db import get_db
from financial_health_app.models.household import Household
from financial_health_app.models.household_invitation import HouseholdInvitation
from financial_health_app.models.user import User
from financial_health_app.templating import templates

router = APIRouter()

_SESSION_COOKIE = "session"
_ALREADY_HAS_HOUSEHOLD_ERROR = "Ya perteneces a un hogar"
_NO_HOUSEHOLD_ERROR = "No perteneces a ningún hogar todavía"
_INVALID_NAME_ERROR = (
    "El nombre del hogar no puede estar vacío ni superar 100 caracteres"
)
_INVALID_CODE_ERROR = "Código de invitación inválido o caducado"
_INVITE_CODE_EXPIRY = timedelta(hours=24)


def _current_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        return None
    return validate_session(db, token)


def _validate_household_name(name: str) -> str | None:
    stripped = name.strip()
    if not stripped or len(stripped) > 100:
        return _INVALID_NAME_ERROR
    return None


def create_household(db: Session, *, user_id: int, name: str) -> Household | None:
    """Crea el hogar y asocia al usuario como ADM, de forma atómica (FR-005/FR-008).

    No hace commit — el llamador controla la transacción. Devuelve None si el
    usuario ya tenía un hogar — detectado por la `UPDATE` condicional
    (`WHERE household_id IS NULL`), que también cierra la ventana de carrera de
    dos peticiones simultáneas de creación del mismo usuario (spec-critic hallazgo
    2): si la `UPDATE` afecta 0 filas, el `INSERT` de `households` de esta función
    queda pendiente de deshacer por el llamador (no se comete), sin dejar un hogar
    huérfano.
    """
    household = Household(name=name.strip(), created_by=user_id)
    db.add(household)
    db.flush()

    result = cast(
        CursorResult,
        db.execute(
            update(User)
            .where(User.id == user_id, User.household_id.is_(None))
            .values(household_id=household.id, permission_level_code="ADM")
        ),
    )
    if result.rowcount == 0:
        return None
    return household


@router.get("/household")
def household_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    if user.household_id is None:
        return templates.TemplateResponse(
            request, "household.html", {"household": None}
        )

    household = db.get(Household, user.household_id)
    return templates.TemplateResponse(
        request,
        "household.html",
        {
            "household": household,
            "permission_level_code": user.permission_level_code,
        },
    )


@router.post("/household/create")
def household_create(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    user = _current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    if user.household_id is not None:
        return templates.TemplateResponse(
            request,
            "household.html",
            {"household": None, "error": _ALREADY_HAS_HOUSEHOLD_ERROR},
            status_code=409,
        )

    error = _validate_household_name(name)
    if error:
        return templates.TemplateResponse(
            request,
            "household.html",
            {"household": None, "error": error},
            status_code=422,
        )

    household = create_household(db, user_id=user.id, name=name)
    if household is None:
        # create_household() no hizo commit de su INSERT pendiente — deshacerlo
        # aquí para no dejar un hogar huérfano (spec-critic hallazgo 2).
        db.rollback()
        return templates.TemplateResponse(
            request,
            "household.html",
            {"household": None, "error": _ALREADY_HAS_HOUSEHOLD_ERROR},
            status_code=409,
        )

    db.commit()
    return RedirectResponse("/household", status_code=303)


def consume_invitation(db: Session, *, invitation_id: int, user_id: int) -> bool:
    """Marca la invitación como usada de forma atómica (FR-006 — garantía de
    concurrencia). No hace commit — el llamador controla la transacción.

    Devuelve True si esta llamada ganó la carrera de consumo, False si ya estaba
    usada (por otra petición concurrente con el mismo código, o porque ya se
    había consumido antes de llegar aquí).
    """
    result = cast(
        CursorResult,
        db.execute(
            update(HouseholdInvitation)
            .where(
                HouseholdInvitation.id == invitation_id,
                HouseholdInvitation.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC), used_by=user_id)
        ),
    )
    return result.rowcount > 0


@router.post("/household/join")
def household_join(
    request: Request,
    code: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    user = _current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    if user.household_id is not None:
        return templates.TemplateResponse(
            request,
            "household.html",
            {"household": None, "error": _ALREADY_HAS_HOUSEHOLD_ERROR},
            status_code=409,
        )

    # Auto-reseteo si el bloqueo ya expiró (mismo criterio que login.py de 001).
    if user.invite_locked_until is not None and not check_invite_lockout(user):
        reset_invite_lockout(user)

    if check_invite_lockout(user):
        record_invite_attempt(db, user_id=user.id, household_id=None, result="locked")
        db.commit()
        return templates.TemplateResponse(
            request,
            "household.html",
            {"household": None, "error": _INVALID_CODE_ERROR},
            status_code=401,
        )

    code_hash = hash_code(code)
    now = datetime.now(UTC)
    invitation = db.scalars(
        select(HouseholdInvitation).where(
            HouseholdInvitation.code_hash == code_hash,
            HouseholdInvitation.used_at.is_(None),
            HouseholdInvitation.expires_at > now,
        )
    ).one_or_none()

    if invitation is not None:
        won = consume_invitation(db, invitation_id=invitation.id, user_id=user.id)
    else:
        won = False

    if not won:
        register_failed_invite_attempt(db, user)
        # Búsqueda secundaria, solo para fines de auditoría (FR-015, spec-critic
        # hallazgo 1): identifica household_id si el código corresponde a una
        # invitación real ya usada/caducada, distinto de un código inexistente.
        household_id_for_audit = (
            invitation.household_id if invitation is not None else None
        )
        if household_id_for_audit is None:
            stale = db.scalars(
                select(HouseholdInvitation).where(
                    HouseholdInvitation.code_hash == code_hash
                )
            ).first()
            household_id_for_audit = stale.household_id if stale is not None else None
        record_invite_attempt(
            db, user_id=user.id, household_id=household_id_for_audit, result="failure"
        )
        db.commit()
        return templates.TemplateResponse(
            request,
            "household.html",
            {"household": None, "error": _INVALID_CODE_ERROR},
            status_code=401,
        )

    # `won` solo es True cuando `invitation` no es None (ver ramas de arriba).
    assert invitation is not None
    user.household_id = invitation.household_id
    user.permission_level_code = "MEM"
    reset_invite_lockout(user)
    record_invite_attempt(
        db, user_id=user.id, household_id=invitation.household_id, result="success"
    )
    db.commit()
    return RedirectResponse("/household", status_code=303)


@router.post("/household/invite")
def household_invite(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    if user.household_id is None:
        return templates.TemplateResponse(
            request,
            "household.html",
            {"household": None, "error": _NO_HOUSEHOLD_ERROR},
            status_code=409,
        )

    code = generate_code()
    invitation = HouseholdInvitation(
        household_id=user.household_id,
        code_hash=hash_code(code),
        expires_at=datetime.now(UTC) + _INVITE_CODE_EXPIRY,
        created_by=user.id,
    )
    db.add(invitation)
    db.commit()

    household = db.get(Household, user.household_id)
    return templates.TemplateResponse(
        request,
        "household.html",
        {
            "household": household,
            "permission_level_code": user.permission_level_code,
            "invite_code": code,
        },
    )
