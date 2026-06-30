from pydantic import BaseModel
from datetime import datetime
from typing import Literal


class BackendModel(BaseModel):
    id: str
    provider: Literal["openai", "anthropic"]
    api_base: str
    api_key: str
    model_name: str
    rpm: int = 120


class ModelGroup(BaseModel):
    name: str
    models: list[str]
    weights: dict[str, float]
    fallback: str | None = None


class ApiKey(BaseModel):
    key_hash: str
    name: str
    models: list[str] | None = None
    created_at: datetime | None = None
