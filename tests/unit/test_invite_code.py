"""Tests unitarios de auth/invite_code.py (ADR-0006)."""

import string

from financial_health_app.auth.invite_code import generate_code, hash_code, verify_code

_AMBIGUOUS = set("0O1Il")


def test_generate_code_has_8_characters() -> None:
    code = generate_code()
    assert len(code) == 8


def test_generate_code_uses_only_unambiguous_alphanumeric_characters() -> None:
    code = generate_code()
    allowed = set(string.ascii_uppercase + string.digits) - _AMBIGUOUS
    assert set(code) <= allowed


def test_generate_code_produces_different_values() -> None:
    codes = {generate_code() for _ in range(50)}
    assert len(codes) > 1


def test_hash_code_is_deterministic() -> None:
    code = "ABCD2345"
    assert hash_code(code) == hash_code(code)


def test_hash_code_differs_for_different_codes() -> None:
    assert hash_code("ABCD2345") != hash_code("ZYXW9876")


def test_hash_code_does_not_contain_the_code_in_clear() -> None:
    code = "ABCD2345"
    assert code not in hash_code(code)


def test_verify_code_accepts_matching_pair() -> None:
    code = "ABCD2345"
    assert verify_code(code, hash_code(code)) is True


def test_verify_code_rejects_wrong_code() -> None:
    assert verify_code("WRONG123", hash_code("ABCD2345")) is False
