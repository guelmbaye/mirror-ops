"""Construction du `id_token` attendu par l'authentification S2S Perfect Corp.

Le secret client ne se transmet PAS en clair : la console fournit une cle
publique RSA, et l'API attend une chaine `client_secret=<secret>&timestamp=<ms>`
chiffree avec cette cle puis encodee en base64.

C'est le point qui distingue cette authentification d'un `client_credentials`
OAuth ordinaire. Envoyer le secret tel quel produit un rejet cote provider — et,
plus haut dans la pile, un `ANALYSIS_FAILED` sans cause lisible.
"""

from __future__ import annotations

import base64
import time

from app.integrations.youcam.exceptions import YouCamAuthError

# En-tetes PEM tolerees : la console peut livrer la cle sous plusieurs formes.
_PEM_HEADERS = ("-----BEGIN PUBLIC KEY-----", "-----BEGIN RSA PUBLIC KEY-----")

INSTALL_HINT = (
    "The `cryptography` package is required for YouCam client_credentials auth. "
    "Install it with: pip install -r requirements.txt "
    "(outside a venv: pip install cryptography --break-system-packages)"
)


def crypto_available() -> bool:
    """Verifiable au demarrage, plutot que decouvert au milieu d'un parcours."""
    try:
        import cryptography  # noqa: F401
    except ImportError:
        return False
    return True


def normalize_public_key(raw: str) -> str:
    """Accepte une cle PEM complete, ou seulement son corps base64.

    Les cles collees depuis une console arrivent souvent sur une seule ligne,
    sans en-tetes : on les reconstruit plutot que d'echouer sur un detail de
    presse-papiers.
    """
    key = (raw or "").strip().replace("\\n", "\n")
    if not key:
        raise YouCamAuthError(
            "Missing YOUCAM_SECRET_KEY: the RSA public key from the YouCam console is required "
            "for client_credentials authentication."
        )
    if any(header in key for header in _PEM_HEADERS):
        return key

    body = "".join(key.split())
    wrapped = "\n".join(body[i : i + 64] for i in range(0, len(body), 64))
    return f"-----BEGIN PUBLIC KEY-----\n{wrapped}\n-----END PUBLIC KEY-----"


def build_id_token(client_secret: str, public_key_pem: str, *, timestamp_ms: int | None = None) -> str:
    """Chiffre le secret et l'horodatage, puis encode en base64."""
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
    except ImportError as exc:  # pragma: no cover - dependance declaree
        raise YouCamAuthError(INSTALL_HINT) from exc

    if not client_secret:
        raise YouCamAuthError("Missing YOUCAM_CLIENT_SECRET")

    stamp = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    payload = f"client_secret={client_secret}&timestamp={stamp}".encode()

    try:
        key = serialization.load_pem_public_key(normalize_public_key(public_key_pem).encode())
    except YouCamAuthError:
        raise
    except Exception as exc:
        raise YouCamAuthError("YOUCAM_SECRET_KEY is not a readable RSA public key", detail=str(exc))

    if not isinstance(key, rsa.RSAPublicKey):
        raise YouCamAuthError("YOUCAM_SECRET_KEY must be an RSA public key")

    # PKCS#1 v1.5 : le schema attendu par l'API S2S.
    try:
        encrypted = key.encrypt(payload, padding.PKCS1v15())
    except ValueError as exc:
        raise YouCamAuthError(
            "Client secret is too long for this RSA key", detail=str(exc)
        )
    return base64.b64encode(encrypted).decode()
