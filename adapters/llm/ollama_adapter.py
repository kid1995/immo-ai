import json

import httpx

from core.ports import LLMMessage, LLMResponse


class OllamaAdapter:
    """Implements LLMPort Protocol using the Ollama HTTP API."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
    ) -> None:
        self._base_url = base_url
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

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": api_messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()

        return LLMResponse(
            content=data["message"]["content"],
            model=self._model,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
        )

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        output_schema: type,
        system: str | None = None,
    ) -> object:
        """Ask Ollama to return JSON matching the schema, then validate."""
        schema_json = json.dumps(output_schema.model_json_schema(), indent=2)
        structured_system = (
            f"{system or ''}\n\n"
            f"You MUST respond with valid JSON matching this schema:\n{schema_json}\n"
            "Return ONLY the JSON object, no other text."
        ).strip()

        result = await self.complete(
            messages=messages,
            system=structured_system,
            max_tokens=4096,
        )

        raw = json.loads(result.content)
        return output_schema.model_validate(raw)
