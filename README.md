# LLM Proxy

Lightweight LLM proxy with OpenAI/Anthropic compatible interfaces, model grouping, weighted routing, retry/cooldown/fallback.

## Install

```bash
pip install llm-proxy
```

## Quick Start

```bash
llm-proxy --port 4001 --admin-key my-key
llm-admin model add --id gpt4o --provider openai --api-base https://api.openai.com/v1 --api-key sk-xxx --model-name gpt-4o
llm-admin group add --name fast --models gpt4o --weights 100
llm-admin key add --name my-app --models fast
```

## License

MIT
