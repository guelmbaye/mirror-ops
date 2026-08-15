"""Configuration centrale de MIRROR OPS.

Toute la configuration (API, YouCam, scoring, stockage) est centralisée ici,
conformement au Doc 07 §18 : "Centraliser : API settings / YouCam settings /
Scoring weights / Thresholds / Storage / Environment".
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # UN SEUL fichier, volontairement : apps/api/.env.
        #
        # Le .env racine sert exclusivement a docker-compose et n'est PAS lu
        # ici. Deux fichiers alimentant le meme processus creaient un piege :
        # pydantic-settings donne la priorite au dernier declare, si bien que le
        # .env racine ecrasait silencieusement le mode YouCam configure dans
        # celui de l'application.
        #
        # Sous Docker, compose passe de vraies variables d'environnement, qui
        # priment de toute facon sur ce fichier.
        # Chemin ABSOLU, ancre sur le paquet.
        #
        # `".env"` est resolu depuis le repertoire courant : l'API lancee depuis
        # apps/api lisait la bonne configuration, un script lance depuis la
        # racine lisait celle de docker-compose — sans cle YouCam. La sonde
        # rapportait alors « Missing YOUCAM_API_KEY » tout en affichant
        # « mode : live », et le diagnostic accusait la photo.
        #
        # Meme classe de defaut que les cles d'idempotence : un resultat qui
        # depend d'ou l'on se tient est un resultat faux la moitie du temps.
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ app
    APP_NAME: str = "MIRROR OPS API"
    APP_ENV: Literal["development", "test", "staging", "production"] = "development"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    # ------------------------------------------------------------- security
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    MEDIA_SIGNING_SECRET: str = "change-me-in-production"
    RATE_LIMIT_PER_MINUTE: int = 120
    RATE_LIMIT_ENABLED: bool = True

    # ------------------------------------------------------------- database
    DATABASE_URL: str = "sqlite+aiosqlite:///./mirror_ops.db"
    DB_ECHO: bool = False

    # ---------------------------------------------------------- sessions/TTL
    SESSION_TTL_MINUTES: int = 120
    MEDIA_TTL_MINUTES: int = 120

    # --------------------------------------------------------------- images
    MAX_IMAGE_BYTES: int = 10 * 1024 * 1024  # 10 MB (Doc 08 §6)
    ALLOWED_IMAGE_MIME: str = "image/jpeg,image/png,image/webp"
    MIN_IMAGE_WIDTH: int = 320
    MIN_IMAGE_HEIGHT: int = 320
    MAX_IMAGE_PIXELS: int = 40_000_000

    # -------------------------------------------------------------- storage
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_DIR: str = "./var/storage"
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET: str | None = None
    S3_REGION: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None

    # --------------------------------------------------------------- YouCam
    # mode=mock -> aucun appel reseau, resultats explicitement marques "mock".
    # mode=live -> appels reels vers l'API YouCam (Perfect Corp S2S).
    YOUCAM_MODE: Literal["mock", "live"] = "mock"
    YOUCAM_API_BASE_URL: str = "https://yce-api-01.makeupar.com"
    # v2 = `api_key` (recommande). `client_credentials` ne sert qu'a l'API v1.
    YOUCAM_AUTH_MODE: Literal["api_key", "client_credentials"] = "api_key"
    YOUCAM_API_KEY: str | None = None
    YOUCAM_CLIENT_ID: str | None = None
    YOUCAM_CLIENT_SECRET: str | None = None
    # Cle publique RSA fournie par la console YouCam ("Secret key").
    # Sert a chiffrer le id_token : le secret client ne circule jamais en clair.
    YOUCAM_SECRET_KEY: str | None = None
    # --- API v2 (recommandee) -------------------------------------------
    # v2 supprime l'endpoint d'authentification : la cle API part directement
    # en Bearer. Le nom de la fonctionnalite est « cloth », au singulier.
    YOUCAM_AUTH_PATH: str = "/s2s/v1.0/client/auth"
    YOUCAM_SKIN_FILE_PATH: str = "/s2s/v2.0/file/skin-analysis"
    YOUCAM_SKIN_TASK_PATH: str = "/s2s/v2.0/task/skin-analysis"
    YOUCAM_VTO_FILE_PATH: str = "/s2s/v2.0/file/cloth"
    YOUCAM_VTO_TASK_PATH: str = "/s2s/v2.0/task/cloth"
    # v2 interroge l'etat d'une tache par GET {path}/{task_id} ; v1 le passait
    # en parametre de requete.
    YOUCAM_TASK_ID_IN_PATH: bool = True
    # `json` renvoie les scores dans la reponse ; `zip` renvoie une archive.
    YOUCAM_SKIN_RESULT_FORMAT: str = "json"
    # SD plutot que HD : HD exige un cote court >= 1080 px, qu'un cadrage de
    # visage extrait d'une photo de tenue atteint rarement. HD et SD ne se
    # melangent jamais dans une meme requete.
    YOUCAM_SKIN_ACTIONS: str = "redness,oiliness,texture,radiance"
    # Recadrer le visage avant d'appeler Skin AI (voir services/face_crop.py).
    SKIN_FACE_CROP_ENABLED: bool = True
    YOUCAM_TIMEOUT_MS: int = 30_000
    YOUCAM_MAX_RETRIES: int = 2
    YOUCAM_RETRY_BACKOFF_MS: int = 400
    YOUCAM_POLL_INTERVAL_MS: int = 1_200
    YOUCAM_POLL_TIMEOUT_MS: int = 90_000
    YOUCAM_CACHE_TTL_SECONDS: int = 900  # Doc 05 §20 : cache court

    # ----------------------------------------------- ONE CHANGE engine knobs
    ONE_CHANGE_THRESHOLD: float = 60.0          # Doc 04 §14
    ONE_CHANGE_NO_CHANGE_MARGIN: float = 2.0    # marge minimale vs NO_CHANGE
    ONE_CHANGE_TIE_DELTA: float = 5.0           # Doc 04 §16
    ONE_CHANGE_MIN_DATA_CONFIDENCE: float = 0.35  # Data Quality Gate (Doc 04 §20)

    # ------------------------------------------------------------- helpers
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_mime_list(self) -> list[str]:
        return [m.strip() for m in self.ALLOWED_IMAGE_MIME.split(",") if m.strip()]

    @property
    def skin_action_list(self) -> list[str]:
        return [a.strip() for a in self.YOUCAM_SKIN_ACTIONS.split(",") if a.strip()]

    @property
    def is_live_youcam(self) -> bool:
        return self.YOUCAM_MODE == "live"

    @property
    def has_youcam_credentials(self) -> bool:
        if self.YOUCAM_AUTH_MODE == "api_key":
            return bool(self.YOUCAM_API_KEY)
        # `client_credentials` exige aussi la cle publique : sans elle, le
        # id_token ne peut pas etre construit et l'appel sera rejete.
        return bool(
            self.YOUCAM_CLIENT_ID and self.YOUCAM_CLIENT_SECRET and self.YOUCAM_SECRET_KEY
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
