from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingPort(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    async def embed_many(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimensions(self) -> int:
        """Vector size – must match pgvector column definition."""
        ...
