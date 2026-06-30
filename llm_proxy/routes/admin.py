import hashlib
import json
import secrets
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from llm_proxy.config import settings

router = APIRouter(prefix="/admin")
_db = None


def init_routes(db):
    global _db
    _db = db


async def _verify_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing admin key")
    key = auth[7:]
    expected = settings.admin_api_key
    if not expected:
        raise HTTPException(status_code=500, detail="Admin API key not configured")
    if not secrets.compare_digest(key, expected):
        raise HTTPException(status_code=403, detail="Invalid admin key")


class AddModelRequest(BaseModel):
    id: str
    provider: str
    api_base: str
    api_key: str
    model_name: str
    rpm: int = 120


@router.get("/models")
async def list_models(request: Request):
    await _verify_admin(request)
    backends = await _db.list_backends()
    return {"data": backends}


@router.post("/models")
async def add_model(request: Request, body: AddModelRequest):
    await _verify_admin(request)
    await _db.add_backend(id=body.id, provider=body.provider, api_base=body.api_base,
                          api_key=body.api_key, model_name=body.model_name, rpm=body.rpm)
    return {"status": "ok", "id": body.id}


@router.delete("/models/{model_id}")
async def delete_model(request: Request, model_id: str):
    await _verify_admin(request)
    await _db.delete_backend(model_id)
    return {"status": "ok"}


class AddGroupRequest(BaseModel):
    name: str
    models: list[str]
    weights: list[float]
    fallback: str | None = None


@router.get("/groups")
async def list_groups(request: Request):
    await _verify_admin(request)
    groups = await _db.list_groups()
    return {"data": groups}


@router.post("/groups")
async def add_group(request: Request, body: AddGroupRequest):
    await _verify_admin(request)
    for model_id in body.models:
        backend = await _db.get_backend(model_id)
        if not backend:
            raise HTTPException(status_code=400, detail=f"Model '{model_id}' not found")
    await _db.add_group(name=body.name, fallback=body.fallback)
    for model_id, weight in zip(body.models, body.weights):
        await _db.add_group_member(body.name, model_id, weight)
    return {"status": "ok", "name": body.name}


@router.delete("/groups/{group_name}")
async def delete_group(request: Request, group_name: str):
    await _verify_admin(request)
    await _db.delete_group(group_name)
    return {"status": "ok"}


@router.put("/groups/{group_name}/fallback")
async def set_fallback(request: Request, group_name: str, fallback: str):
    await _verify_admin(request)
    existing = await _db.get_group(group_name)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Group '{group_name}' not found")
    await _db.add_group(name=group_name, fallback=fallback)
    return {"status": "ok"}


class AddKeyRequest(BaseModel):
    name: str
    models: list[str] | None = None


@router.get("/keys")
async def list_keys(request: Request):
    await _verify_admin(request)
    keys = await _db.list_api_keys()
    return {"data": keys}


@router.post("/keys")
async def add_key(request: Request, body: AddKeyRequest):
    await _verify_admin(request)
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    models_json = json.dumps(body.models) if body.models else None
    await _db.add_api_key(key_hash=key_hash, name=body.name, models=models_json)
    return {"status": "ok", "name": body.name, "key": raw_key, "hash": key_hash}


@router.delete("/keys/{name}")
async def delete_key(request: Request, name: str):
    await _verify_admin(request)
    keys = await _db.list_api_keys()
    for k in keys:
        if k["name"] == name:
            await _db.delete_api_key(k["key_hash"])
            return {"status": "ok"}
    raise HTTPException(status_code=404, detail=f"Key '{name}' not found")


@router.get("/stats")
async def get_stats(request: Request, since: str = None, until: str = None, group_by: str = "model"):
    await _verify_admin(request)
    stats = await _db.get_usage_stats(since=since, until=until, group_by=group_by)
    summary = await _db.get_usage_summary(since=since, until=until)
    return {"summary": summary, "details": stats}
