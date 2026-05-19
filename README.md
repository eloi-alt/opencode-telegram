# OpenCode Telegram Bridge

Self-hosted Telegram bridge for [OpenCode](https://github.com/anomalyco/opencode). Send prompts from Telegram, get responses back — with persistent sessions per chat, full state tracking, and clean runtime abstraction.

## Architecture

```
Telegram ──► Webhook ──► FastAPI ──► UseCase ──► OpenCodeRuntime
                 ▲                        │          ├── API Adapter
                 │                        │          ├── CLI Adapter
                 │                        ▼          └── Fake Adapter (dev)
                 └── TelegramClient ◄── Response
```

## Quick Start

```bash
# Install
pip install opencode-telegram

# Set your bot token
export TELEGRAM_BOT_TOKEN="your_token_from_botfather"

# Run
opencode-telegram
```

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | required | Bot token from BotFather |
| `OPENCODE_MODE` | `cli` | `api` or `cli` |
| `OPENCODE_CLI_PATH` | `opencode` | Path to opencode binary |
| `OPENCODE_BASE_URL` | — | API base URL (API mode) |
| `OPENCODE_API_KEY` | — | API key (API mode) |
| `TELEGRAM_ALLOWED_USERS` | — | Comma-separated user IDs |
| `TELEGRAM_ALLOWED_CHATS` | — | Comma-separated chat IDs |
| `PORT` | `8080` | HTTP server port |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/opencode-telegram.db` | Persistence |
| `SESSION_TIMEOUT_SEC` | `1800` | Stale session timeout |

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Show system status |
| `/status` | Current session state |
| `/sessions` | List active sessions |
| `/resume` | Pick a session to resume |
| `/clear` | Clear current session context |
| `/stop` | Interrupt running execution |
| `/health` | Detailed diagnostics (admin) |
| `/logs` | Recent events (admin) |
| `/help` | Show help |

## Webhook Setup

```bash
# Set webhook once
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=https://your-public-url/webhook"

# Verify
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

## Docker

```bash
docker compose -f docker/docker-compose.yml up -d
```

## Development

```bash
# Fake runtime (no OpenCode needed)
export FAKE_RUNTIME=true
opencode-telegram

# Run tests
pytest
```

## Documentation

See `docs/` for detailed guides:
- `architecture.md` — Architecture and component design
- `configuration.md` — Full configuration reference
- `deployment.md` — Deployment scenarios
- `security.md` — Security model
- `migration-notes.md` — Differences from Claude Code bridge
