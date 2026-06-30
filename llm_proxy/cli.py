"""LLM Proxy Server CLI."""
import argparse
import uvicorn
from llm_proxy.config import settings


def main():
    parser = argparse.ArgumentParser(prog="llm-proxy", description="LLM Proxy Server")
    parser.add_argument("--host", default=None, help="Listen host")
    parser.add_argument("--port", type=int, default=None, help="Listen port")
    parser.add_argument("--db", default=None, help="SQLite database path")
    parser.add_argument("--admin-key", default=None, help="Admin API key")
    args = parser.parse_args()
    if args.host is not None:
        settings.host = args.host
    if args.port is not None:
        settings.port = args.port
    if args.db is not None:
        settings.db_path = args.db
    if args.admin_key is not None:
        settings.admin_api_key = args.admin_key
    uvicorn.run("llm_proxy.main:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
