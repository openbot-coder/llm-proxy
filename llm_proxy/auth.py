import hashlib
from llm_proxy.database import Database
from llm_proxy.models import ApiKey


async def verify_api_key(key: str, db: Database) -> ApiKey | None:
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    row = await db.get_api_key(key_hash)
    if not row:
        return None
    return ApiKey(key_hash=row["key_hash"], name=row["name"], models=row.get("models"))
