"""Test unitario de hashing.py: round-trip Argon2id y mitigación de timing
(ADR-0004)."""

import time

from financial_health_app.auth.hashing import (
    hash_password,
    verify_password,
    verify_password_timing_safe,
)


def test_hash_password_roundtrip_verifies_correct_password() -> None:
    hashed = hash_password("Segura123!")
    assert verify_password("Segura123!", hashed) is True


def test_hash_password_rejects_wrong_password() -> None:
    hashed = hash_password("Segura123!")
    assert verify_password("Incorrecta456!", hashed) is False


def test_hash_password_is_not_the_plaintext() -> None:
    hashed = hash_password("Segura123!")
    assert hashed != "Segura123!"
    assert "Segura123!" not in hashed


def test_verify_password_timing_safe_with_hash_returns_verification_result() -> None:
    hashed = hash_password("Segura123!")
    assert verify_password_timing_safe("Segura123!", hashed) is True
    assert verify_password_timing_safe("Incorrecta456!", hashed) is False


def test_verify_password_timing_safe_without_hash_returns_false() -> None:
    assert verify_password_timing_safe("cualquier-password", None) is False


def test_verify_password_timing_safe_without_hash_does_full_argon2_work() -> None:
    """El coste computacional de verificar contra el hash dummy debe ser comparable
    al de una verificación real, no un atajo inmediato (mitigación de enumeración
    por timing, SC-002).
    """
    hashed = hash_password("Segura123!")

    start_real = time.perf_counter()
    verify_password_timing_safe("Incorrecta456!", hashed)
    real_duration = time.perf_counter() - start_real

    start_dummy = time.perf_counter()
    verify_password_timing_safe("cualquier-password", None)
    dummy_duration = time.perf_counter() - start_dummy

    # El camino "sin hash" debe tardar al menos una fracción sustancial del camino
    # real (no debe ser órdenes de magnitud más rápido, lo que delataría un atajo
    # sin trabajo Argon2id).
    assert dummy_duration > real_duration * 0.3
