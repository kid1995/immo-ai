import json

import openai

from core.ports import LLMMessage, LLMResponse


class OpenAIAdapter:
    """Implements LLMPort Protocol using the OpenAI SDK."""

    def __init__(self, *, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    async def complete(
        self,
        messages: list[LLMMessage],
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        api_messages: list[dict] = []
        if system is not None:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend({"role": m.role, "content": m.content} for m in messages)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        output_schema: type,
        system: str | None = None,
    ) -> object:
        """Use function calling to get structured output."""
        schema = output_schema.model_json_schema()

        function_def = {
            "type": "function",
            "function": {
                "name": "structured_output",
                "description": "Return structured data matching the schema.",
                "parameters": schema,
            },
        }

        api_messages: list[dict] = []
        if system is not None:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend({"role": m.role, "content": m.content} for m in messages)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            tools=[function_def],
            tool_choice={"type": "function", "function": {"name": "structured_output"}},
            max_tokens=4096,
        )

        choice = response.choices[0]
        if choice.message.tool_calls:
            raw = json.loads(choice.message.tool_calls[0].function.arguments)
            return output_schema.model_validate(raw)

        msg = "No tool call in response"
        raise ValueError(msg)
