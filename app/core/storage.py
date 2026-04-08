"""
Media storage abstraction — local filesystem or S3-compatible.

Usage:
    storage = get_storage(settings)
    url = await storage.upload(data, filename, content_type)
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import uuid4


class StorageBackend(Protocol):
    async def upload(self, data: bytes, filename: str, content_type: str, base_url: str = "") -> str:
        """Upload file and return its public URL."""
        ...


class LocalStorage:
    """Saves files to local disk and returns a /media/... URL."""

    def __init__(self, media_root: str):
        self.media_root = Path(media_root)

    async def upload(self, data: bytes, filename: str, content_type: str, base_url: str = "") -> str:
        upload_dir = self.media_root / "profile-photos"
        upload_dir.mkdir(parents=True, exist_ok=True)
        dest = upload_dir / filename
        dest.write_bytes(data)
        return f"{base_url.rstrip('/')}/media/profile-photos/{filename}"


class S3Storage:
    """Uploads files to S3-compatible storage and returns a public URL."""

    def __init__(
        self,
        bucket: str,
        region: str,
        access_key: str,
        secret_key: str,
        endpoint_url: str = "",
    ):
        self.bucket = bucket
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint_url = endpoint_url or None
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3

            kwargs = {
                "service_name": "s3",
                "region_name": self.region,
                "aws_access_key_id": self.access_key,
                "aws_secret_access_key": self.secret_key,
            }
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            self._client = boto3.client(**kwargs)
        return self._client

    async def upload(self, data: bytes, filename: str, content_type: str, base_url: str = "") -> str:
        import asyncio

        key = f"profile-photos/{filename}"
        client = self._get_client()

        # Run boto3 sync call in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                ACL="public-read",
            ),
        )

        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket}/{key}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"


_storage: StorageBackend | None = None


def get_storage(settings=None) -> StorageBackend:
    """Return storage backend based on settings. Re-creates if settings differ."""
    global _storage

    if settings is None:
        if _storage is not None:
            return _storage
        from app.core.config import get_settings
        settings = get_settings()

    if settings.storage_backend == "s3" and settings.s3_bucket:
        _storage = S3Storage(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            endpoint_url=settings.s3_endpoint_url,
        )
    else:
        _storage = LocalStorage(media_root=settings.media_root)

    return _storage
