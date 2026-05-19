# Configuration

All configuration is via environment variables or `.env` file. Validated at startup by Pydantic.

## Required

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather |

## Runtime Mode

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCODE_MODE` | `cli` | `api` or `cli` |
| `OPENCODE_CLI_PATH` | `opencode` | Path to opencode binary (CLI mode) |
| `OPENCODE_BASE_URL` | — | OpenCode API base URL (API mode) |
| `OPENCODE_API_KEY` | — | API key (API mode) |
| `OPENCODE_WORKSPACE_ROOT` | `~/opencode/workspaces` | Workspace root directory |
| `OPENCODE_DEFAULT_WORKSPACE` | `default` | Default workspace name |
| `OPENCODE_DEFAULT_SERVER` | `local` | Default server name |

## Security

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_ALLOWED_USERS` | — | Comma-separated Telegram user IDs (empty = all) |
| `TELEGRAM_ALLOWED_CHATS` | — | Comma-separated chat IDs (empty = all) |
| `ENABLE_ADMIN_COMMANDS` | `true` | Enable /health and /logs |
| `ENABLE_DANGEROUS_COMMANDS` | `false` | Enable exec/shell/bash/sudo commands |

## Server

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | HTTP server port |
| `APP_BASE_URL` | — | Public URL (for webhook reference) |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL) |

## Persistence

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///data/opencode-telegram.db` | Database URL |
| `STORAGE_PATH` | `./data` | File storage path |

## Session

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_TIMEOUT_SEC` | `1800` | Stale session timeout (seconds) |
| `MESSAGE_MAX_LENGTH` | `4096` | Maximum Telegram message length |

## Health

| Variable | Default | Description |
|----------|---------|-------------|
| `HEALTHCHECK_INTERVAL_SEC` | `60` | Health check interval |

## Example `.env`

```bash
TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
OPENCODE_MODE="cli"
OPENCODE_CLI_PATH="opencode"
OPENCODE_DEFAULT_WORKSPACE="my-project"
TELEGRAM_ALLOWED_USERS="12345678,87654321"
LOG_LEVEL="INFO"
PORT="8080"
```

## Development Mode

Set `FAKE_RUNTIME=true` to use the in-memory fake OpenCode adapter — no real OpenCode needed for development.
