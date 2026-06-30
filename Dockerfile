FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml .

RUN uv sync --no-dev --no-install-project

COPY llm_proxy/ llm_proxy/

EXPOSE 4001

CMD ["uv", "run", "llm-proxy", "--host", "0.0.0.0", "--port", "4001"]
