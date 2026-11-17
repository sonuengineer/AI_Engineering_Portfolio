"""Object storage abstraction. LocalStorage for dev; an S3-compatible implementation is the
production path (see docs/deployment.md). Keys are content-addressed and org-scoped."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes) -> str: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("Invalid storage key")
        return p

    def put(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    """S3 / S3-compatible object storage (AWS S3, MinIO, Ceph, R2).

    Keys are the same content-addressed, org-prefixed keys as LocalStorage. Objects are written with
    server-side encryption (AES256) when talking to AWS; S3-compatible stores that do not support
    the header can disable it with sse=None.
    """

    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str | None = None,
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        sse: str | None = "AES256",
        client: Any = None,
    ):
        import boto3

        self.bucket = bucket
        self.sse = sse
        self._s3 = client or boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
        )

    @staticmethod
    def _check(key: str) -> str:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise ValueError("Invalid storage key")
        return key

    def put(self, key: str, data: bytes) -> str:
        extra = {"ServerSideEncryption": self.sse} if self.sse else {}
        self._s3.put_object(Bucket=self.bucket, Key=self._check(key), Body=data, **extra)
        return key

    def get(self, key: str) -> bytes:
        try:
            obj = self._s3.get_object(Bucket=self.bucket, Key=self._check(key))
        except self._s3.exceptions.NoSuchKey as exc:
            raise FileNotFoundError(key) from exc
        body: bytes = obj["Body"].read()
        return body

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self.bucket, Key=self._check(key))  # idempotent in S3

    def ensure_bucket(self) -> None:
        existing = {b["Name"] for b in self._s3.list_buckets().get("Buckets", [])}
        if self.bucket not in existing:
            self._s3.create_bucket(Bucket=self.bucket)


def get_storage() -> ObjectStorage:
    from app.core.config import get_settings

    s = get_settings()
    if s.storage_backend == "s3":
        on_aws = not s.s3_endpoint_url
        return S3Storage(
            s.s3_bucket,
            endpoint_url=s.s3_endpoint_url,
            region=s.s3_region,
            access_key_id=s.s3_access_key_id,
            secret_access_key=s.s3_secret_access_key,
            sse="AES256" if on_aws else None,
        )
    configured = get_settings().storage_dir or os.environ.get("STORAGE_DIR")
    return LocalStorage(configured or Path(__file__).resolve().parents[2] / "var" / "objects")


def prepare_storage() -> None:
    """Startup hook: make sure the S3 bucket exists (no-op for local storage)."""
    store = get_storage()
    if isinstance(store, S3Storage):
        store.ensure_bucket()
