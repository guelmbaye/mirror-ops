"""Integration YouCam : toute la complexite provider reste dans ce package."""

from app.integrations.youcam.auth import INSTALL_HINT, build_id_token, crypto_available
from app.integrations.youcam.exceptions import (
    diagnostics,
    YouCamAuthError,
    YouCamError,
    YouCamInvalidImageError,
    YouCamProviderError,
    YouCamQuotaExhaustedError,
    YouCamRateLimitError,
    YouCamResultUnavailableError,
    YouCamTimeoutError,
    YouCamValidationError,
)
from app.integrations.youcam.models import GarmentRef, SkinAnalysisResult, VTOGenerationResult
from app.integrations.youcam.provider import (
    SkinProvider,
    VTOProvider,
    get_skin_provider,
    get_vto_provider,
    reset_providers,
    set_providers,
)

__all__ = [
    "crypto_available",
    "build_id_token",
    "INSTALL_HINT",
    "diagnostics",
    "GarmentRef",
    "SkinAnalysisResult",
    "SkinProvider",
    "VTOGenerationResult",
    "VTOProvider",
    "YouCamAuthError",
    "YouCamError",
    "YouCamInvalidImageError",
    "YouCamProviderError",
    "YouCamQuotaExhaustedError",
    "YouCamRateLimitError",
    "YouCamResultUnavailableError",
    "YouCamTimeoutError",
    "YouCamValidationError",
    "get_skin_provider",
    "get_vto_provider",
    "reset_providers",
    "set_providers",
]
