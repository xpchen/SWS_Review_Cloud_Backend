import os
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from ..settings import settings


class LocalStorage:
    """Store files under LOCAL_STORAGE_DIR. Signed URL = BASE_URL + /storage/ + key (served by API)."""

    def __init__(self):
        self.root = Path(settings.LOCAL_STORAGE_DIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key.replace("/", os.sep)

    def put(self, key: str, file_like: BinaryIO, content_type: str | None = None, size: int | None = None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            while True:
                chunk = file_like.read(65536)
                if not chunk:
                    break
                f.write(chunk)

    def get_signed_url(self, key: str, expires_in_seconds: int = 1800) -> str:
        # Local: return URL to API route that serves the file
        base = settings.BASE_URL.rstrip("/")
        return f"{base}/storage/{key}"

    def get_object(self, key: str) -> BinaryIO | None:
        path = self._path(key)
        if not path.is_file():
            return None
        return open(path, "rb")

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()
