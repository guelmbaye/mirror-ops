"""Stockage media temporaire (Doc 05 §21, Doc 07 §12).

Cycle de vie : upload -> stockage temporaire -> traitement -> resultat ->
fin de session -> cleanup. Les octets ne sont jamais stockes en base.
"""

from __future__ import annotations

import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger("mirror_ops.storage")


class ObjectStorage(ABC):
    @abstractmethod
    async def put(self, key: str, data: bytes, content_type: str) -> str: ...

    @abstractmethod
    async def get(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> int: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...


class LocalObjectStorage(ObjectStorage):
    """Stockage disque local : suffisant pour le hackathon (Doc 07 §3)."""

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or get_settings().STORAGE_DIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise AppError(ErrorCode.INVALID_REQUEST, "Invalid storage key.")
        return candidate

    async def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise AppError(ErrorCode.NOT_FOUND, "This media is no longer available.")
        return path.read_bytes()

    async def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    async def delete_prefix(self, prefix: str) -> int:
        target = self._path(prefix)
        if target.is_dir():
            count = sum(1 for _ in target.rglob("*") if _.is_file())
            shutil.rmtree(target, ignore_errors=True)
            return count
        if target.is_file():
            target.unlink(missing_ok=True)
            return 1
        return 0


class S3ObjectStorage(ObjectStorage):
    """Stockage S3 / R2 / MinIO (optionnel : necessite `boto3`)."""

    def __init__(self) -> None:
        settings = get_settings()
        try:
            import boto3  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - dependance optionnelle
            raise RuntimeError("STORAGE_BACKEND=s3 requires the 'boto3' package") from exc
        self._bucket = settings.S3_BUCKET
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        )

    async def put(self, key: str, data: bytes, content_type: str) -> str:  # pragma: no cover
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return key

    async def get(self, key: str) -> bytes:  # pragma: no cover
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    async def exists(self, key: str) -> bool:  # pragma: no cover
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:  # noqa: BLE001
            return False

    async def delete_prefix(self, prefix: str) -> int:  # pragma: no cover
        paginator = self._client.get_paginator("list_objects_v2")
        deleted = 0
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            objects = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if objects:
                self._client.delete_objects(Bucket=self._bucket, Delete={"Objects": objects})
                deleted += len(objects)
        return deleted


_storage: ObjectStorage | None = None


def get_storage() -> ObjectStorage:
    global _storage
    if _storage is None:
        settings = get_settings()
        _storage = S3ObjectStorage() if settings.STORAGE_BACKEND == "s3" else LocalObjectStorage()
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None


def session_key(session_id: str, kind: str, filename: str) -> str:
    """sessions/{session_id}/{input|vto}/{filename} — Doc 07 §12."""
    return f"sessions/{session_id}/{kind}/{filename}"
