"""Le `id_token` doit etre dechiffrable par le detenteur de la cle privee."""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.integrations.youcam.auth import build_id_token, normalize_public_key
from app.integrations.youcam.exceptions import YouCamAuthError


@pytest.fixture(scope="module")
def keypair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private, public_pem


def test_id_token_round_trips(keypair):
    private, public_pem = keypair
    token = build_id_token("super-secret", public_pem, timestamp_ms=1735689600000)

    decrypted = private.decrypt(base64.b64decode(token), padding.PKCS1v15()).decode()
    assert decrypted == "client_secret=super-secret&timestamp=1735689600000"


def test_id_token_is_never_the_raw_secret(keypair):
    _, public_pem = keypair
    token = build_id_token("super-secret", public_pem)
    assert "super-secret" not in token
    assert token != "super-secret"


def test_two_calls_differ_because_of_the_timestamp(keypair):
    _, public_pem = keypair
    assert build_id_token("s", public_pem, timestamp_ms=1) != build_id_token(
        "s", public_pem, timestamp_ms=2
    )


def test_key_pasted_without_pem_headers_is_repaired(keypair):
    _, public_pem = keypair
    body = "".join(line for line in public_pem.splitlines() if "-----" not in line)

    private, _ = keypair
    token = build_id_token("secret", body, timestamp_ms=7)
    decrypted = private.decrypt(base64.b64decode(token), padding.PKCS1v15()).decode()
    assert decrypted == "client_secret=secret&timestamp=7"


def test_escaped_newlines_from_dotenv_are_handled(keypair):
    private, public_pem = keypair
    single_line = public_pem.replace("\n", "\\n")
    token = build_id_token("secret", single_line, timestamp_ms=9)
    decrypted = private.decrypt(base64.b64decode(token), padding.PKCS1v15()).decode()
    assert decrypted == "client_secret=secret&timestamp=9"


def test_missing_key_says_exactly_what_is_missing():
    with pytest.raises(YouCamAuthError) as caught:
        normalize_public_key("")
    assert "YOUCAM_SECRET_KEY" in str(caught.value)


def test_garbage_key_is_reported_clearly():
    with pytest.raises(YouCamAuthError) as caught:
        build_id_token("secret", "not-a-key-at-all")
    assert "RSA public key" in str(caught.value)


def test_missing_cryptography_is_detected_before_any_request(monkeypatch):
    """Une dependance absente doit se voir au demarrage, pas au premier 502."""
    import builtins

    from app.integrations.youcam import auth

    real_import = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name == "cryptography":
            raise ImportError("simulated absence")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    assert auth.crypto_available() is False


def test_the_install_hint_names_the_command_to_run():
    from app.integrations.youcam.auth import INSTALL_HINT

    assert "pip install" in INSTALL_HINT
    assert "cryptography" in INSTALL_HINT


async def test_health_reports_a_missing_dependency(client, monkeypatch):
    from app.api.v1.routes import health as health_route
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "YOUCAM_MODE", "live", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_AUTH_MODE", "client_credentials", raising=False)
    monkeypatch.setattr(health_route, "crypto_available", lambda: False)

    body = (await client.get("/api/v1/health/dependencies")).json()
    assert body["youcam"] == "missing_dependency"
