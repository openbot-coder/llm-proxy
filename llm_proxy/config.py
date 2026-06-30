from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 4001
    db_path: str = "llm_proxy.db"
    fail_threshold: int = 2
    cooldown_seconds: int = 900
    admin_api_key: str = ""
    base_url: str = "http://localhost:4001"

    model_config = {"env_prefix": "LLM_PROXY_"}


settings = Settings()
