from contextlib import asynccontextmanager
from fastapi import FastAPI
from llm_proxy.config import settings
from llm_proxy.database import Database
from llm_proxy.routes.openai import router as openai_router, init_routes as init_openai
from llm_proxy.routes.anthropic import router as anthropic_router, init_routes as init_anthropic
from llm_proxy.routes.admin import router as admin_router, init_routes as init_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database(settings.db_path)
    await db.init()
    app.state.db = db
    init_openai(db)
    init_anthropic(db)
    init_admin(db)
    yield
    await db.close()


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Proxy", lifespan=lifespan)
    app.include_router(openai_router)
    app.include_router(anthropic_router)
    app.include_router(admin_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
