from abc import ABC, abstractmethod


class EmbeddingPort(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_many(self, texts: list[str]) -> list[list[float]]: ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Vector size – must match pgvector column definition."""
        ...
