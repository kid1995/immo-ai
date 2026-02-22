from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


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


@runtime_checkable
class LLMPort(Protocol):
    async def complete(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        output_schema: type,
        system: str | None = None,
    ) -> Any:
        """Return structured output validated against a Pydantic model."""
        ...
