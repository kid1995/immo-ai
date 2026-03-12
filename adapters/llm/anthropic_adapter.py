import json

import anthropic

from core.ports import LLMMessage, LLMResponse


class AnthropicAdapter:
    """Implements LLMPort Protocol using the Anthropic SDK."""

    def __init__(self, *, api_key: str, model: str = "claude-sonnet-4-5") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict = {
            "model": self._model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system is not None:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        output_schema: type,
        system: str | None = None,
    ) -> object:
        """Use tool_use to get structured output validated against a Pydantic model."""
        schema = output_schema.model_json_schema()

        tool_definition = {
            "name": "structured_output",
            "description": "Return structured data matching the schema.",
            "input_schema": schema,
        }

        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict = {
            "model": self._model,
            "messages": api_messages,
            "tools": [tool_definition],
            "tool_choice": {"type": "tool", "name": "structured_output"},
            "max_tokens": 4096,
        }
        if system is not None:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)

        for block in response.content:
            if block.type == "tool_use":
                raw = block.input
                if isinstance(raw, str):
                    raw = json.loads(raw)
                return output_schema.model_validate(raw)

        msg = "No tool_use block in response"
        raise ValueError(msg)
