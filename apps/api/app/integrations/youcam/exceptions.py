"""Taxonomie d'erreurs du provider (Doc 05 §17).

Le reste de l'application ne connait QUE ces exceptions : jamais httpx,
jamais un status code YouCam, jamais un payload provider brut.
"""

from __future__ import annotations


class YouCamError(Exception):
    """Erreur generique du provider visuel."""

    retryable: bool = False
    code: str = "PROVIDER_ERROR"

    def __init__(
        self, message: str = "", *, detail: str | None = None, provider_code: str | None = None
    ) -> None:
        super().__init__(message or self.code)
        self.detail = detail
        #: Code d'erreur renvoye par le provider (`error_pose`, `error_no_face`...).
        #: C'est lui qui permet de dire a l'utilisateur quoi corriger.
        self.provider_code = provider_code


class YouCamValidationError(YouCamError):
    code = "VALIDATION_ERROR"


class YouCamAuthError(YouCamError):
    code = "AUTH_ERROR"


class YouCamRateLimitError(YouCamError):
    code = "RATE_LIMIT"
    retryable = False  # Doc 05 §18 : on ne retry pas un rate limit


class YouCamTimeoutError(YouCamError):
    code = "TIMEOUT"
    retryable = True


class YouCamProviderError(YouCamError):
    code = "PROVIDER_ERROR"
    retryable = True


class YouCamInvalidImageError(YouCamError):
    code = "INVALID_IMAGE"


class YouCamResultUnavailableError(YouCamError):
    code = "RESULT_UNAVAILABLE"
    retryable = True


class YouCamQuotaExhaustedError(YouCamError):
    code = "QUOTA_EXHAUSTED"
    retryable = False


def diagnostics(error: YouCamError, provider: str) -> dict[str, str]:
    """Ce qu'il faut pour comprendre un echec provider, sans rien exposer d'inutile.

    Le `detail` est deja tronque a 200 caracteres par le client, et le logging
    assainit les cles sensibles. Sans ces champs, un 502 ne dit rien de plus que
    « ca n'a pas marche » — insuffisant quand les chemins d'endpoints dependent
    du compte YouCam utilise.
    """
    return {
        "provider": provider,
        "error_code": error.code,
        "error_class": type(error).__name__,
        "reason": str(error),
        "detail": (error.detail or "")[:200],
        "provider_code": error.provider_code or "",
    }
