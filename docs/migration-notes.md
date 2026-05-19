# Migration Notes: Claude Code Bridge → OpenCode Bridge

This document explains the key differences between the original `claudecode-telegram` bridge and the new `opencode-telegram` bridge.

## Why a New Architecture?

The original bridge (`bridge.py`, 285 lines) was a monolithic script tightly coupled to Claude Code's specific runtime behaviors:

| Aspect | Claude Code Bridge | OpenCode Bridge |
|--------|-------------------|-----------------|
| Architecture | Single file, all logic mixed | Hexagonal, 7 layers |
| Runtime coupling | Direct tmux + Claude CLI | `AgentRuntime` interface |
| Session model | Implicit (tmux session) | Explicit state machine |
| Persistence | Flat files | SQLite + repositories |
| Error handling | Minimal try/except | Structured error hierarchy |
| Security | None | Allowlists + rate limiting + validation |
| Testability | None | Full test suite with mocks |
| Observability | print() statements | Structured logging + audit trail |
| Configuration | 3 env vars | 20+ validated settings |

## What Changed

### Removed (Claude-Specific)
- **Stop hook mechanism**: `send-to-telegram.sh` relied on Claude Code's transcript JSONL format. Removed entirely.
- **Ralph Loop**: `/loop` command and `/ralph-loop` prompt injection. Claude-specific feature.
- **Blocked commands list**: 15 Claude-specific commands (`/mcp`, `/model`, `/doctor`, etc.)
- **`~/.claude/` paths**: All references to Claude's directory layout
- **`claude --resume` / `claude --continue`**: Claude CLI flags replaced by `OpenCodeRuntime` methods
- **tmux dependency**: No longer required (CLI adapter uses `asyncio.subprocess`)

### Added (OpenCode-Native)
- **`OpenCodeRuntime` interface**: Clean abstraction for API, CLI, or fake adapters
- **Session state machine**: 9 explicit states with transitions
- **Repository pattern**: 8 repository interfaces for persistence
- **Message status tracking**: 9 statuses from webhook_received to telegram_send_failed
- **Structured logging**: JSON logs with correlation IDs
- **Audit trail**: Every critical event is logged and queryable
- **Health endpoints**: `/health`, `/ready`, `/metrics`
- **Security layer**: Allowlists, rate limiting, admin commands, dangerous command blocklist
- **Configuration validation**: Pydantic-based, 20+ validated settings
- **Docker support**: Multi-stage Dockerfile + docker-compose
- **Fake runtime**: Development without real OpenCode

### Preserved (Reimplemented Better)
- Telegram webhook receiving → FastAPI with structured validation
- Message sending to runtime → `OpenCodeRuntime.send_prompt()`
- Typing indicator → `TelegramClient.send_typing()`
- Inline keyboards → Clean callback handling in `TelegramUpdateHandler`
- Session resume → `/resume` with inline keyboard, persisted bindings

## Backward Compatibility

The new bridge is **not backward-compatible** with the old Claude Code bridge:
- Different database schema (SQLite vs flat files)
- Different configuration (env vars renamed and expanded)
- Different runtime interface (no Stop hook, no tmux)
- Different project structure (modular package vs single script)

## Migration Path

1. If you were using the original `claudecode-telegram`:
   - Old sessions in `~/.claude/` are not migrated
   - Old bot commands (Ralph Loop, etc.) are not available
   - You need to set up OpenCode separately (via CLI or API)
2. Configuration is now via `.env` file — use `.env.example` as template
3. Webhook URL stays the same (`POST /webhook`)
4. The bot will have different commands — run `/help` after migration
