"""Object storage abstraction. LocalStorage for dev; an S3-compatible implementation is the
production path (see docs/deployment.md). Keys are content-addressed and org-scoped."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


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


def get_storage() -> ObjectStorage:
    from app.core.config import get_settings

    configured = get_settings().storage_dir or os.environ.get("STORAGE_DIR")
    return LocalStorage(configured or Path(__file__).resolve().parents[2] / "var" / "objects")
