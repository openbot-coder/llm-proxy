from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class Backend(ABC):
    @abstractmethod
    async def chat_completions(self, messages: list[dict], model: str, **kwargs) -> dict:
        ...

    @abstractmethod
    async def stream_chat(self, messages: list[dict], model: str, **kwargs) -> AsyncIterator[dict]:
        ...
