"""Client HTTP YouCam (Perfect Corp S2S) — Doc 05 §3/§17/§18.

Responsabilites :
- authentification et cache du token ;
- timeouts, retries bornes avec backoff (uniquement erreurs transitoires) ;
- upload de fichiers, creation de taches, polling ;
- traduction de TOUTE erreur reseau/provider en `YouCamError`.

La cle API ne quitte jamais le backend.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.integrations.youcam.auth import build_id_token
from app.integrations.youcam.exceptions import (
    YouCamAuthError,
    YouCamInvalidImageError,
    YouCamProviderError,
    YouCamQuotaExhaustedError,
    YouCamRateLimitError,
    YouCamResultUnavailableError,
    YouCamTimeoutError,
    YouCamValidationError,
)
from app.integrations.youcam.mappers import (
    IMAGE_TASK_ERRORS,
    extract_status,
    extract_task_error,
    extract_task_id,
)

logger = logging.getLogger("mirror_ops.youcam")

_TERMINAL_SUCCESS = {"success", "succeeded", "completed", "done", "finished"}
_TERMINAL_FAILURE = {"error", "failed", "failure", "rejected"}


class YouCamClient:
    """Client bas niveau. Une instance par processus suffit."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = get_settings()
        self._client = http_client
        self._owns_client = http_client is None
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._auth_lock = asyncio.Lock()

    # ------------------------------------------------------------ lifecycle
    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.YOUCAM_API_BASE_URL,
                timeout=httpx.Timeout(self._settings.YOUCAM_TIMEOUT_MS / 1000.0),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    # ----------------------------------------------------------------- auth
    async def _access_token(self) -> str:
        if self._settings.YOUCAM_AUTH_MODE == "api_key":
            if not self._settings.YOUCAM_API_KEY:
                raise YouCamAuthError("Missing YOUCAM_API_KEY")
            return self._settings.YOUCAM_API_KEY

        async with self._auth_lock:
            if self._token and time.time() < self._token_expires_at - 30:
                return self._token
            if not (self._settings.YOUCAM_CLIENT_ID and self._settings.YOUCAM_CLIENT_SECRET):
                raise YouCamAuthError("Missing YouCam client credentials")

            # Le secret ne part jamais en clair : il est chiffre avec la cle
            # publique RSA de la console, comme l'exige l'authentification S2S.
            payload = {
                "client_id": self._settings.YOUCAM_CLIENT_ID,
                "id_token": build_id_token(
                    self._settings.YOUCAM_CLIENT_SECRET or "",
                    self._settings.YOUCAM_SECRET_KEY or "",
                ),
            }
            data = await self._request_json(
                "POST", self._settings.YOUCAM_AUTH_PATH, json=payload, authenticated=False
            )
            result = data.get("result", data)
            token = result.get("access_token") or result.get("token")
            if not token:
                raise YouCamAuthError("No access token in provider response")
            ttl = float(result.get("expires_in", 3600))
            self._token = str(token)
            self._token_expires_at = time.time() + ttl
            return self._token

    async def _headers(self, authenticated: bool = True) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {await self._access_token()}"
        return headers

    # -------------------------------------------------------------- request
    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        client = await self._http()
        attempts = self._settings.YOUCAM_MAX_RETRIES + 1
        backoff = self._settings.YOUCAM_RETRY_BACKOFF_MS / 1000.0
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                response = await client.request(
                    method,
                    path,
                    json=json,
                    params=params,
                    headers=await self._headers(authenticated),
                )
            except httpx.TimeoutException as exc:
                last_error = YouCamTimeoutError("Provider timeout", detail=str(exc))
            except httpx.HTTPError as exc:
                last_error = YouCamProviderError("Provider transport error", detail=str(exc))
            else:
                error = self._error_for_status(response)
                if error is None:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise YouCamProviderError("Malformed provider payload", detail=str(exc))
                if not error.retryable:
                    raise error
                last_error = error

            if attempt < attempts - 1:
                await asyncio.sleep(backoff * (2**attempt))
                logger.warning(
                    "youcam_retry",
                    extra={"path": path, "attempt": attempt + 1, "method": method},
                )

        assert last_error is not None
        raise last_error

    @staticmethod
    def _error_for_status(response: httpx.Response):
        status = response.status_code
        if status < 400:
            return None
        snippet = response.text[:200] if response.text else ""
        if status in (401, 403):
            return YouCamAuthError("Provider rejected credentials", detail=snippet)
        if status == 429:
            return YouCamRateLimitError("Provider rate limit", detail=snippet)
        if status == 402:
            return YouCamQuotaExhaustedError("Provider quota exhausted", detail=snippet)
        if status == 413:
            return YouCamInvalidImageError("Image rejected by provider", detail=snippet)
        if status in (400, 422):
            lowered = snippet.lower()
            if "image" in lowered or "file" in lowered:
                return YouCamInvalidImageError("Image rejected by provider", detail=snippet)
            return YouCamValidationError("Invalid provider request", detail=snippet)
        if status == 504 or status == 408:
            return YouCamTimeoutError("Provider timeout", detail=snippet)
        return YouCamProviderError(f"Provider error {status}", detail=snippet)

    # --------------------------------------------------------------- upload
    async def request_upload_slot(self, path: str, *, file_name: str, content_type: str, size: int) -> dict:
        payload = {
            "files": [{"content_type": content_type, "file_name": file_name, "file_size": size}]
        }
        return await self._request_json("POST", path, json=payload)

    async def upload_bytes(self, upload_url: str, data: bytes, content_type: str, headers: dict | None = None) -> None:
        client = await self._http()
        merged = {"Content-Type": content_type}
        merged.update(headers or {})
        try:
            response = await client.put(upload_url, content=data, headers=merged)
        except httpx.TimeoutException as exc:
            raise YouCamTimeoutError("Upload timeout", detail=str(exc))
        except httpx.HTTPError as exc:
            raise YouCamProviderError("Upload transport error", detail=str(exc))
        error = self._error_for_status(response)
        if error is not None:
            raise error

    async def download_bytes(self, url: str) -> bytes:
        client = await self._http()
        try:
            response = await client.get(url)
        except httpx.TimeoutException as exc:
            raise YouCamTimeoutError("Result download timeout", detail=str(exc))
        except httpx.HTTPError as exc:
            raise YouCamProviderError("Result download error", detail=str(exc))
        error = self._error_for_status(response)
        if error is not None:
            raise error
        return response.content

    # ---------------------------------------------------------------- tasks
    async def create_task(self, path: str, payload: dict) -> str:
        data = await self._request_json("POST", path, json=payload)
        task_id = extract_task_id(data)
        if not task_id:
            raise YouCamProviderError("Provider did not return a task id")
        return task_id

    async def poll_task(self, path: str, task_id: str) -> dict:
        """Attend la fin d'une tache asynchrone (Doc 05 §14). Polling cote backend."""
        settings = self._settings
        deadline = time.monotonic() + settings.YOUCAM_POLL_TIMEOUT_MS / 1000.0
        interval = settings.YOUCAM_POLL_INTERVAL_MS / 1000.0

        # v2 : GET {path}/{task_id}. v1 : task_id en parametre de requete.
        in_path = getattr(settings, "YOUCAM_TASK_ID_IN_PATH", True)
        poll_path = f"{path.rstrip('/')}/{task_id}" if in_path else path
        params = None if in_path else {"task_id": task_id}

        while True:
            data = await self._request_json("GET", poll_path, params=params)
            status = extract_status(data)
            if status in _TERMINAL_SUCCESS:
                return data
            if status in _TERMINAL_FAILURE:
                code, message = extract_task_error(data)
                detail = " ".join(part for part in (code, message) if part) or None
                # Un probleme de photo n'est pas une panne de service : le dire
                # correctement permet a l'utilisateur de reprendre son cliche.
                error_type = (
                    YouCamInvalidImageError
                    if code in IMAGE_TASK_ERRORS
                    else YouCamProviderError
                )
                raise error_type(
                    f"Provider task failed ({status})", detail=detail, provider_code=code
                )
            if time.monotonic() >= deadline:
                raise YouCamTimeoutError("Provider task did not complete in time")
            await asyncio.sleep(interval)


_client: YouCamClient | None = None


def get_youcam_client() -> YouCamClient:
    global _client
    if _client is None:
        _client = YouCamClient()
    return _client


async def close_youcam_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


__all__ = [
    "YouCamClient",
    "close_youcam_client",
    "get_youcam_client",
    "YouCamResultUnavailableError",
]
