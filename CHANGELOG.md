# Changelog

## [0.1.0] - 2026-06-30

### Added
- OpenAI compatible API (`/v1/chat/completions`, `/v1/models`)
- Anthropic compatible API (`/v1/messages`)
- Admin API for remote management
- Model grouping with weighted random routing
- Retry, cooldown, and fallback mechanism
- Streaming support (SSE) for both protocols
- API Key authentication (SHA256 hashed)
- Usage statistics tracking
- CLI tools: `llm-proxy` and `llm-admin`
- Docker support with Dockerfile
- SQLite storage with WAL mode
- 40 passing tests
