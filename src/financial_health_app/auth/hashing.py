"""Hashing de contraseñas con Argon2id (ADR-0002) y mitigación de timing (ADR-0004)."""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()

# Hash dummy precalculado a nivel de módulo (nunca corresponde a una contraseña
# real). Usado por verify_password_timing_safe cuando el usuario no existe, para que
# la verificación consuma el mismo coste computacional que un intento contra un
# usuario real (ADR-0004).
_DUMMY_HASH = _hasher.hash("dummy-password-para-mitigar-enumeracion-por-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def verify_password_timing_safe(password: str, hash_or_none: str | None) -> bool:
    """Verifica `password` contra `hash_or_none`.

    Si `hash_or_none` es None (identificador inexistente), verifica igualmente
    contra un hash dummy y devuelve False — nunca "corta antes" del trabajo
    Argon2id, para no crear una diferencia de tiempo observable frente al caso de
    password incorrecta contra un usuario real (mitigación de enumeración de
    usuarios por timing, SC-002, ADR-0004).
    """
    if hash_or_none is None:
        verify_password(password, _DUMMY_HASH)
        return False
    return verify_password(password, hash_or_none)
