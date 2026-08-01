"""Object storage abstraction: local disk (dev/tests) or S3-compatible.

All document bytes live behind ``get_storage()``; swapping MinIO for Alibaba
OSS / Azure Blob in production is a configuration change only.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
from pathlib import Path

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class StorageError(RuntimeError):
    pass


class Storage:
    """Minimal async object-store interface (put / get / delete)."""

    async def put(self, key: str, data: bytes) -> None:
        raise NotImplementedError

    async def get(self, key: str) -> bytes:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        # Keys are server-generated (uuid-based); keep them confined to the root.
        return self._root / key

    async def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise StorageError(f"Object not found: {key}")
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            await asyncio.to_thread(path.unlink)


class S3Storage(Storage):
    def __init__(self, settings: Settings) -> None:
        from minio import Minio

        self._client = Minio(
            settings.s3_endpoint.replace("http://", "").replace("https://", ""),
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=settings.s3_endpoint.startswith("https"),
        )
        self._bucket = settings.s3_bucket
        self._bucket_ready = False

    async def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        if not await asyncio.to_thread(self._client.bucket_exists, self._bucket):
            await asyncio.to_thread(self._client.make_bucket, self._bucket)
        self._bucket_ready = True

    async def put(self, key: str, data: bytes) -> None:
        await self._ensure_bucket()
        try:
            await asyncio.to_thread(
                self._client.put_object,
                self._bucket,
                key,
                io.BytesIO(data),
                length=len(data),
            )
        except Exception as exc:
            raise StorageError(f"S3 put failed for {key}: {exc}") from exc

    async def get(self, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(self._client.get_object, self._bucket, key)
            return await asyncio.to_thread(response.read)
        except Exception as exc:
            raise StorageError(f"S3 get failed for {key}: {exc}") from exc

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(self._client.remove_object, self._bucket, key)
        except Exception as exc:
            logger.warning("S3 delete failed for %s: %s", key, exc)


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_storage(settings: Settings | None = None) -> Storage:
    settings = settings or get_settings()
    backend = settings.storage_backend.lower()
    if backend == "local":
        return LocalStorage(settings.local_storage_root)
    if backend in ("auto", "s3"):
        if settings.s3_endpoint:
            return S3Storage(settings)
        return LocalStorage(settings.local_storage_root)
    raise StorageError(f"Unknown storage backend: {settings.storage_backend}")
