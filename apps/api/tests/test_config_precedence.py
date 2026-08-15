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
    """Une seule source de verite : apps/api/.env, par chemin absolu.

    Deux fichiers alimentant le meme processus creaient un piege — le dernier
    declare gagne, et le .env racine remettait YOUCAM_MODE a `mock`. Un chemin
    relatif en creait un second : le fichier lu dependait du repertoire
    courant, si bien qu'un script lance depuis la racine n'avait pas de cle.
    """
    from pathlib import Path

    configured = Settings.model_config["env_file"]
    assert isinstance(configured, str)
    path = Path(configured)
    assert path.is_absolute(), f"relative env_file resolves against the CWD: {configured}"
    assert path.name == ".env"
    assert path.parent.name == "api"


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


def test_a_stray_env_file_nearby_is_ignored(tmp_path, monkeypatch):
    """Scenario exact du bug : un `.env` dans le repertoire courant.

    Avec un chemin relatif, se placer dans un dossier contenant un `.env`
    suffisait a changer la configuration de l'API. Le fichier de l'application
    est desormais lu par chemin absolu : ce qui traine ailleurs n'a plus
    d'effet.
    """
    monkeypatch.delenv("YOUCAM_MODE", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("YOUCAM_MODE=live\n", encoding="utf-8")

    from pathlib import Path

    real = Path(Settings.model_config["env_file"])
    expected = "live" if "YOUCAM_MODE=live" in real.read_text(encoding="utf-8") else "mock"
    assert Settings().YOUCAM_MODE == expected


def test_the_env_file_is_found_whatever_the_working_directory(tmp_path, monkeypatch):
    """`env_file=".env"` etait resolu depuis le repertoire courant.

    L'API lancee depuis apps/api lisait la bonne configuration ; un script lance
    depuis la racine du depot lisait celle de docker-compose, sans cle YouCam.
    La sonde annoncait alors « mode : live » puis echouait sur
    « Missing YOUCAM_API_KEY », et le diagnostic accusait la photo.
    """
    from pathlib import Path

    from app.core.config import Settings

    configured = Path(Settings.model_config["env_file"])
    assert configured.is_absolute(), configured
    assert configured.parent.name == "api"

    monkeypatch.chdir(tmp_path)
    from_elsewhere = Settings()
    monkeypatch.chdir(configured.parent)
    from_home = Settings()

    assert from_elsewhere.YOUCAM_MODE == from_home.YOUCAM_MODE
    assert from_elsewhere.DATABASE_URL == from_home.DATABASE_URL


def test_process_environment_still_wins(monkeypatch):
    """Docker passe la configuration par variables : elles priment sur le fichier."""
    from app.core.config import Settings

    monkeypatch.setenv("YOUCAM_MODE", "live")
    monkeypatch.setenv("YOUCAM_API_KEY", "from-environment")
    settings = Settings()
    assert settings.YOUCAM_MODE == "live"
    assert settings.YOUCAM_API_KEY == "from-environment"
