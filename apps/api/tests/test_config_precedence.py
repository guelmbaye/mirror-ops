"""Precedence de configuration.

Un `.env` racine (destine a docker-compose) ne doit JAMAIS ecraser le `.env` de
l'application. Ce test existe parce que l'inverse s'est produit : le mode YouCam
etait remis a `mock` a l'insu de l'utilisateur, et l'ecran final affichait
« simulated preview » alors que les identifiants live etaient bien renseignes.
"""

from __future__ import annotations

import os

from app.core.config import Settings


def test_the_api_reads_exactly_one_env_file():
    """Une seule source de verite : apps/api/.env.

    Deux fichiers alimentant le meme processus creaient un piege — le dernier
    declare gagne, et le .env racine remettait YOUCAM_MODE a `mock`.
    """
    assert Settings.model_config["env_file"] == ".env"


def test_the_app_env_file_is_honoured(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUCAM_MODE", raising=False)
    monkeypatch.delenv("YOUCAM_CLIENT_ID", raising=False)

    env = tmp_path / "app.env"
    env.write_text("YOUCAM_MODE=live\nYOUCAM_CLIENT_ID=real-id\n", encoding="utf-8")

    settings = Settings(_env_file=env)
    assert settings.YOUCAM_MODE == "live"
    assert settings.is_live_youcam is True
    assert settings.YOUCAM_CLIENT_ID == "real-id"


def test_environment_variables_beat_the_env_file(tmp_path, monkeypatch):
    """C'est ainsi que docker-compose injecte sa configuration."""
    env = tmp_path / "app.env"
    env.write_text("YOUCAM_MODE=mock\n", encoding="utf-8")
    monkeypatch.setenv("YOUCAM_MODE", "live")

    settings = Settings(_env_file=env)
    assert settings.YOUCAM_MODE == "live"


def test_live_mode_without_credentials_is_detectable():
    # Mode par defaut : v2, une simple cle API.
    key_missing = Settings(_env_file=None, YOUCAM_MODE="live", YOUCAM_API_KEY="")
    assert key_missing.has_youcam_credentials is False

    live_blank = Settings(
        _env_file=None,
        YOUCAM_MODE="live",
        YOUCAM_AUTH_MODE="client_credentials",
        YOUCAM_CLIENT_ID="",
        YOUCAM_CLIENT_SECRET="",
    )
    assert live_blank.is_live_youcam is True
    assert live_blank.has_youcam_credentials is False

    # `client_credentials` exige aussi la cle publique RSA : sans elle, le
    # id_token ne peut pas etre construit et l'appel serait rejete.
    without_key = Settings(
        _env_file=None,
        YOUCAM_MODE="live",
        YOUCAM_AUTH_MODE="client_credentials",
        YOUCAM_CLIENT_ID="id",
        YOUCAM_CLIENT_SECRET="secret",
    )
    assert without_key.has_youcam_credentials is False

    live_ok = Settings(
        _env_file=None,
        YOUCAM_MODE="live",
        YOUCAM_AUTH_MODE="client_credentials",
        YOUCAM_CLIENT_ID="id",
        YOUCAM_CLIENT_SECRET="secret",
        YOUCAM_SECRET_KEY="-----BEGIN PUBLIC KEY-----\nabc\n-----END PUBLIC KEY-----",
    )
    assert live_ok.has_youcam_credentials is True

    key_mode = Settings(
        _env_file=None, YOUCAM_MODE="live", YOUCAM_AUTH_MODE="api_key", YOUCAM_API_KEY="k"
    )
    assert key_mode.has_youcam_credentials is True


def test_live_mode_selects_the_real_providers(monkeypatch):
    """Le tampon « simulated » ne peut venir que du mode mock."""
    from app.integrations.youcam import provider

    monkeypatch.setattr(provider, "_skin_provider", None, raising=False)
    monkeypatch.setattr(provider, "_vto_provider", None, raising=False)

    settings = provider.get_settings()
    monkeypatch.setattr(settings, "YOUCAM_MODE", "live", raising=False)

    assert provider.get_vto_provider().provider_name == "youcam_apparel_vto"
    assert provider.get_skin_provider().provider_name == "youcam_skin_ai"

    provider.reset_providers()
    monkeypatch.setattr(settings, "YOUCAM_MODE", "mock", raising=False)
    assert provider.get_vto_provider().provider_name == "local_composite"
    provider.reset_providers()


def test_the_root_env_file_cannot_override_the_app_one(tmp_path, monkeypatch):
    """Scenario exact du bug : racine en `mock`, application en `live`."""
    monkeypatch.delenv("YOUCAM_MODE", raising=False)
    monkeypatch.chdir(tmp_path)

    (tmp_path / ".env").write_text("YOUCAM_MODE=live\n", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    (root / ".env").write_text("YOUCAM_MODE=mock\n", encoding="utf-8")

    assert Settings().YOUCAM_MODE == "live"
