"""Unit tests for OpenAI credential encryption."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.openai_credential_service import (
    _mask_openai_api_key,
    decrypt_api_key,
    encrypt_api_key,
)


@pytest.fixture
def encryption_settings():
    m = MagicMock()
    m.jwt_secret = ""
    m.app_secret_key = "unit-test-app-secret-key-32chars-minimum-xx"
    m.openai_api_key = ""
    return m


def test_encrypt_decrypt_roundtrip(encryption_settings: MagicMock) -> None:
    with patch("app.services.openai_credential_service.get_settings", return_value=encryption_settings):
        plain = "sk-proj-fake-key-for-unit-testing-purposes-only-999"
        ct = encrypt_api_key(plain)
        assert ct != plain
        assert decrypt_api_key(ct) == plain


def test_decrypt_fails_with_wrong_master_secret(encryption_settings: MagicMock) -> None:
    with patch("app.services.openai_credential_service.get_settings", return_value=encryption_settings):
        ct = encrypt_api_key("sk-proj-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    other = MagicMock()
    other.jwt_secret = ""
    other.app_secret_key = "different-master-secret-key-xxxxxxxx"
    with patch("app.services.openai_credential_service.get_settings", return_value=other):
        with pytest.raises(ValueError, match="decrypt"):
            decrypt_api_key(ct)


def test_mask_openai_api_key() -> None:
    masked = _mask_openai_api_key("sk-proj-abcdefghijklmnopqrstuvwxyz")
    assert masked.startswith("sk-proj")
    assert "…" in masked
    assert masked.endswith("wxyz")
