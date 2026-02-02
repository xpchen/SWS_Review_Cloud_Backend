from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageBase(ABC):
    @abstractmethod
    def put(self, key: str, file_like: BinaryIO, content_type: str | None = None, size: int | None = None) -> None:
        """Upload object. key follows DDS 5.1 (e.g. projects/1/documents/2/versions/3/source.docx)."""
        ...

    @abstractmethod
    def get_signed_url(self, key: str, expires_in_seconds: int = 1800) -> str:
        """Return a URL that allows temporary access to the object."""
        ...

    @abstractmethod
    def get_object(self, key: str) -> BinaryIO | None:
        """Return a stream to read the object. None if not found."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if object exists."""
        ...
