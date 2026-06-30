import random
from llm_proxy.database import Database
from llm_proxy.retry import RetryManager
from llm_proxy.models import BackendModel


def weighted_random_select(models: list[BackendModel], weights: list[float]) -> BackendModel:
    total = sum(weights)
    if total <= 0:
        return models[0]
    r = random.uniform(0, total)
    cumulative = 0.0
    for model, weight in zip(models, weights):
        cumulative += weight
        if r <= cumulative:
            return model
    return models[-1]


async def select_model(group_name: str, db: Database, retry_manager: RetryManager) -> BackendModel | None:
    group = await db.get_group(group_name)
    if not group:
        return None
    available = []
    for member in group["members"]:
        model_id = member["model_id"]
        if not retry_manager.is_available(model_id):
            continue
        backend_row = await db.get_backend(model_id)
        if not backend_row:
            continue
        available.append((
            BackendModel(id=backend_row["id"], provider=backend_row["provider"],
                         api_base=backend_row["api_base"], api_key=backend_row["api_key"],
                         model_name=backend_row["model_name"], rpm=backend_row["rpm"]),
            member["weight"],
        ))
    if not available:
        if group.get("fallback"):
            return await select_model(group["fallback"], db, retry_manager)
        return None
    models, weights = zip(*available)
    return weighted_random_select(list(models), list(weights))
