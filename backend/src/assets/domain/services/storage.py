from abc import ABC, abstractmethod

from src.common.domain.entities.common.in_memory_file import InMemoryFile


class StorageService(ABC):
    """Object storage port. Methods are async so adapters never block the event loop."""

    @abstractmethod
    async def upload_file(self, input_file: InMemoryFile) -> InMemoryFile:
        raise NotImplementedError

    @abstractmethod
    async def get_file(self, file_path: str) -> InMemoryFile:
        raise NotImplementedError

    @abstractmethod
    async def delete_file(self, file_path: str) -> None:
        raise NotImplementedError
