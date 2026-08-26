"""Generación y hash del código de invitación a hogar (FR-006/FR-007, ADR-0006)."""

import hashlib
import hmac
import os
import secrets

_ALPHABET = "".join(
    c for c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in "0O1IL"
)
_CODE_LENGTH = 8


def generate_code() -> str:
    """Genera un código de 8 caracteres del alfabeto sin ambiguos, vía
    `secrets.choice()` (research.md §1)."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))


def _secret() -> bytes:
    secret = os.environ.get("INVITE_CODE_HMAC_SECRET")
    if not secret:
        raise RuntimeError(
            "INVITE_CODE_HMAC_SECRET no está definida en el entorno (.env)"
        )
    return secret.encode()


def hash_code(code: str) -> str:
    """HMAC-SHA256 determinista del código (ADR-0006) — permite `WHERE code_hash =
    ?` indexado, a diferencia de un hash salteado como Argon2id."""
    return hmac.new(_secret(), code.encode(), hashlib.sha256).hexdigest()


def verify_code(code: str, code_hash: str) -> bool:
    """Comparación en tiempo constante (evita timing attacks)."""
    return hmac.compare_digest(hash_code(code), code_hash)
