import hashlib
import struct


class LocalEmbedding:
    """Implements EmbeddingPort Protocol with deterministic hash-based embeddings.

    For local development and testing only – NOT for production.
    Produces consistent but non-semantic embeddings from text hashes.
    """

    def __init__(self, *, dimensions: int = 1536) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> list[float]:
        return self._hash_embed(text)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_embed(t) for t in texts]

    def _hash_embed(self, text: str) -> list[float]:
        """Generate a deterministic pseudo-embedding from text hash."""
        result: list[float] = []
        iteration = 0
        while len(result) < self._dimensions:
            digest = hashlib.sha512(f"{iteration}:{text}".encode()).digest()
            for i in range(0, 64, 4):
                if len(result) >= self._dimensions:
                    break
                val = struct.unpack("<I", digest[i : i + 4])[0]
                result.append((val / 2_147_483_647.5) - 1.0)
            iteration += 1

        return result[: self._dimensions]
