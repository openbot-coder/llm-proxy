import openai
from collections.abc import AsyncIterator
from llm_proxy.backends.base import Backend


class OpenAIBackend(Backend):
    def __init__(self, api_key: str, base_url: str):
        self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat_completions(self, messages: list[dict], model: str, **kwargs) -> dict:
        resp = await self.client.chat.completions.create(model=model, messages=messages, **kwargs)
        return resp.model_dump()

    async def stream_chat(self, messages: list[dict], model: str, **kwargs) -> AsyncIterator[dict]:
        stream = await self.client.chat.completions.create(model=model, messages=messages, stream=True, **kwargs)
        async for chunk in stream:
            yield chunk.model_dump()
