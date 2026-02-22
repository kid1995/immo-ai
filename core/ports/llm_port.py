from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMMessage:
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMPort(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...

    @abstractmethod
    async def complete_structured(
        self,
        messages: list[LLMMessage],
        output_schema: type,  # Pydantic model
        system: str | None = None,
    ) -> Any:
        """Return structured output validated against a Pydantic model."""
        ...
