from io import BytesIO
from typing import BinaryIO
from urllib.parse import quote, urlparse, urlunparse

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
        url = self.client.presigned_get_object(self.bucket, key, expires=timedelta(seconds=expires_in_seconds))
        # 若配置了 MinIO 代理域名，将返回的 URL 替换为代理地址，便于前端/浏览器访问
        public_base = (settings.MINIO_PUBLIC_URL or "").strip().rstrip("/")
        if public_base:
            parsed = urlparse(url)
            # 保留 path、params、query、fragment，只替换 scheme 和 netloc
            public_parsed = urlparse(public_base)
            scheme = public_parsed.scheme or "https"
            netloc = public_parsed.netloc or public_base.replace("https://", "").replace("http://", "").split("/")[0]
            url = urlunparse((scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        # 确保返回绝对 URL，避免前端当作相对路径拼到当前域名下
        if url and not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url.lstrip("/")
        return url

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
