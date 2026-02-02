from ..settings import settings
from .base import StorageBase
from .local import LocalStorage
from .minio_impl import MinIOStorage


def get_storage() -> StorageBase:
    if settings.STORAGE_TYPE == "minio":
        return MinIOStorage()
    return LocalStorage()
