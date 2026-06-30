import anthropic
from collections.abc import AsyncIterator
from llm_proxy.backends.base import Backend


class AnthropicBackend(Backend):
    def __init__(self, api_key: str, base_url: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url)

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        system = ""
        converted = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                converted.append({"role": msg["role"], "content": msg["content"]})
        return system, converted

    async def chat_completions(self, messages: list[dict], model: str, **kwargs) -> dict:
        system, msgs = self._convert_messages(messages)
        create_kwargs = {"model": model, "messages": msgs, **kwargs}
        if system:
            create_kwargs["system"] = system
        resp = await self.client.messages.create(**create_kwargs)
        return resp.model_dump()

    async def stream_chat(self, messages: list[dict], model: str, **kwargs) -> AsyncIterator[dict]:
        system, msgs = self._convert_messages(messages)
        create_kwargs = {"model": model, "messages": msgs, "max_tokens": kwargs.pop("max_tokens", 4096), **kwargs}
        if system:
            create_kwargs["system"] = system
        async with self.client.messages.stream(**create_kwargs) as stream:
            async for text in stream.text_stream:
                yield {"type": "content_block_delta", "delta": {"text": text}}
