import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from llm_proxy.auth import verify_api_key
from llm_proxy.router import select_model
from llm_proxy.backends import OpenAIBackend, AnthropicBackend
from llm_proxy.retry import RetryManager

router = APIRouter(prefix="/v1")
retry_manager = RetryManager()
_db = None


def init_routes(db):
    global _db
    _db = db


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


async def _verify_and_select(request: Request, model_name: str):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API key")
    key = auth_header[7:]
    api_key = await verify_api_key(key, _db)
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    model = await select_model(model_name, _db, retry_manager)
    if not model:
        raise HTTPException(status_code=503, detail=f"No available model in group '{model_name}'")
    return model


def _make_backend(model):
    if model.provider == "openai":
        return OpenAIBackend(api_key=model.api_key, base_url=model.api_base)
    else:
        return AnthropicBackend(api_key=model.api_key, base_url=model.api_base)


def _format_stream_chunk(chunk: dict, model_id: str) -> str:
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


@router.post("/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest):
    model = await _verify_and_select(request, body.model)
    kwargs = {}
    if body.temperature is not None:
        kwargs["temperature"] = body.temperature
    if body.max_tokens is not None:
        kwargs["max_tokens"] = body.max_tokens
    backend = _make_backend(model)
    if body.stream:
        return StreamingResponse(
            _stream_response(backend, body.messages, model, body.model, _db),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    try:
        result = await backend.chat_completions(body.messages, model.model_name, **kwargs)
        retry_manager.record_success(model.id)
        usage = result.get("usage", {})
        await _db.record_usage(model_id=model.id, provider=model.provider, group_name=body.model,
                               prompt_tokens=usage.get("prompt_tokens", 0),
                               completion_tokens=usage.get("completion_tokens", 0),
                               total_tokens=usage.get("total_tokens", 0))
        return result
    except Exception as e:
        retry_manager.record_failure(model.id)
        raise HTTPException(status_code=502, detail=f"Backend error: {str(e)}")


async def _stream_response(backend, messages, model, group_name, db):
    total_tokens = {"prompt": 0, "completion": 0, "total": 0}
    try:
        async for chunk in backend.stream_chat(messages, model.model_name):
            yield _format_stream_chunk(chunk, model.id)
            usage = chunk.get("usage") or chunk.get("x_openai_usage")
            if usage:
                total_tokens["prompt"] = usage.get("prompt_tokens", 0)
                total_tokens["completion"] = usage.get("completion_tokens", 0)
                total_tokens["total"] = usage.get("total_tokens", 0)
        yield "data: [DONE]\n\n"
        retry_manager.record_success(model.id)
        if total_tokens["total"] > 0:
            await db.record_usage(model_id=model.id, provider=model.provider, group_name=group_name,
                                   prompt_tokens=total_tokens["prompt"],
                                   completion_tokens=total_tokens["completion"],
                                   total_tokens=total_tokens["total"])
    except Exception as e:
        retry_manager.record_failure(model.id)
        error_chunk = {"error": {"message": str(e), "type": "backend_error"}}
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


@router.get("/models")
async def list_models(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API key")
    key = auth_header[7:]
    api_key = await verify_api_key(key, _db)
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    models = []
    groups = await _db.list_groups()
    for g in groups:
        models.append({"id": g["name"], "object": "model", "owned_by": "llm-proxy",
                       "type": "group", "members": [m["model_id"] for m in g.get("members", [])]})
    backends = await _db.list_backends()
    for b in backends:
        models.append({"id": b["id"], "object": "model", "owned_by": b["provider"],
                       "type": "backend", "provider": b["provider"], "model_name": b["model_name"]})
    return {"data": models, "object": "list"}
