import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    generate_verification_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("Tr0ubador", hashed) is False


def test_hash_password_salts_so_same_input_differs() -> None:
    assert hash_password("hunter2") != hash_password("hunter2")


def test_access_token_round_trips_subject() -> None:
    token = create_access_token("user-123")
    assert decode_access_token(token) == "user-123"


def test_decode_rejects_expired_token() -> None:
    token = create_access_token("user-123", expires_minutes=-1)
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_decode_rejects_tampered_token() -> None:
    token = create_access_token("user-123")
    with pytest.raises(TokenError):
        decode_access_token(token + "tampered")


def test_verification_token_hash_matches_and_is_not_the_raw_token() -> None:
    raw, hashed = generate_verification_token()
    assert hashed == hash_token(raw)
    assert hashed != raw
