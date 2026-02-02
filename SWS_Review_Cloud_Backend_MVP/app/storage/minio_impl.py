from io import BytesIO
from typing import BinaryIO
from urllib.parse import quote

from minio import Minio
from minio.error import S3Error

from ..settings import settings
from .base import StorageBase


class MinIOStorage(StorageBase):
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error:
            pass

    def put(self, key: str, file_like: BinaryIO, content_type: str | None = None, size: int | None = None) -> None:
        data = file_like.read() if not hasattr(file_like, "seek") or size is None else file_like
        if isinstance(data, bytes):
            stream = BytesIO(data)
            length = len(data)
        else:
            stream = data
            length = size or -1
        self.client.put_object(
            self.bucket,
            key,
            stream,
            length if length >= 0 else None,
            content_type=content_type or "application/octet-stream",
        )

    def get_signed_url(self, key: str, expires_in_seconds: int = 1800) -> str:
        from datetime import timedelta
        return self.client.presigned_get_object(self.bucket, key, expires=timedelta(seconds=expires_in_seconds))

    def get_object(self, key: str) -> BinaryIO | None:
        try:
            resp = self.client.get_object(self.bucket, key)
            return resp
        except S3Error:
            return None

    def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except S3Error:
            return False
