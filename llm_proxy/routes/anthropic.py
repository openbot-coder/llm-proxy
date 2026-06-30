import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from llm_proxy.auth import verify_api_key
from llm_proxy.router import select_model
from llm_proxy.backends import AnthropicBackend
from llm_proxy.retry import RetryManager

router = APIRouter(prefix="/v1")
retry_manager = RetryManager()
_db = None


def init_routes(db):
    global _db
    _db = db


class MessageRequest(BaseModel):
    model: str
    messages: list[dict]
    max_tokens: int = 4096
    system: str | None = None
    stream: bool = False


@router.post("/messages")
async def messages(request: Request, body: MessageRequest):
    api_key_str = request.headers.get("x-api-key", "")
    if not api_key_str:
        raise HTTPException(status_code=401, detail="Missing API key")
    api_key = await verify_api_key(api_key_str, _db)
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    model = await select_model(body.model, _db, retry_manager)
    if not model:
        raise HTTPException(status_code=503, detail=f"No available model in group '{body.model}'")
    msg_list = body.messages
    if body.system:
        msg_list = [{"role": "system", "content": body.system}] + msg_list
    backend = AnthropicBackend(api_key=model.api_key, base_url=model.api_base)
    if body.stream:
        return StreamingResponse(
            _stream_response(backend, msg_list, model, body.model, body.max_tokens),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    try:
        result = await backend.chat_completions(msg_list, model.model_name, max_tokens=body.max_tokens)
        retry_manager.record_success(model.id)
        usage = result.get("usage", {})
        await _db.record_usage(model_id=model.id, provider=model.provider, group_name=body.model,
                               prompt_tokens=usage.get("input_tokens", 0),
                               completion_tokens=usage.get("output_tokens", 0),
                               total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
        return result
    except Exception as e:
        retry_manager.record_failure(model.id)
        raise HTTPException(status_code=502, detail=f"Backend error: {str(e)}")


async def _stream_response(backend, messages, model, group_name, max_tokens):
    try:
        async for chunk in backend.stream_chat(messages, model.model_name, max_tokens=max_tokens):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        retry_manager.record_success(model.id)
    except Exception as e:
        retry_manager.record_failure(model.id)
        error_chunk = {"error": {"message": str(e), "type": "backend_error"}}
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"
