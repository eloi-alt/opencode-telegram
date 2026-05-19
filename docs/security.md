# Security Model

## 1. Authentication & Authorization

### Bot Token
- The `TELEGRAM_BOT_TOKEN` is the sole credential for Telegram API access
- Keep it secret, use environment variables or a secret manager
- Never commit it to version control

### User/Chat Allowlists
- `TELEGRAM_ALLOWED_USERS`: comma-separated Telegram user IDs
- `TELEGRAM_ALLOWED_CHATS`: comma-separated chat IDs
- When set, any request from non-allowed users/chats is rejected with `401 Unauthorized`
- When empty, all users/chats are allowed (useful for private bots)

### Admin Commands
- `/health` and `/logs` require admin privileges
- Admin = user in `TELEGRAM_ALLOWED_USERS` (when allowlist is enabled)
- Can be fully disabled via `ENABLE_ADMIN_COMMANDS=false`

## 2. Rate Limiting

- Per-key rate limiting with configurable window and max calls
- Default: 10 calls per 60 seconds per key
- Applied to all incoming updates
- Rate limit violations return `429`-equivalent via `UnauthorizedError`

## 3. Dangerous Commands

- Blocked by default: `exec`, `shell`, `bash`, `sh`, `run`, `sudo`
- Can be enabled via `ENABLE_DANGEROUS_COMMANDS=true`
- Even when enabled, commands still go through the `OpenCodeRuntime` adapter (not direct shell)

## 4. Shell Injection Protection

- No user input is ever concatenated into shell commands
- CLI adapter uses `shlex.split()` + `asyncio.create_subprocess_exec()` (never `shell=True`)
- Prompts are sent via stdin, not command-line arguments
- Working directory is controlled and isolated per workspace

## 5. Secret Management

- All secrets via environment variables
- Logging explicitly excludes secret values
- Database stores only non-sensitive configuration
- API keys for OpenCode API mode are sent as HTTP headers, never logged

## 6. Input Validation

- All Telegram webhook payloads are validated at the FastAPI boundary
- Message content is sanitized before formatting
- Commands are parsed with `shlex.split()` for consistent tokenization
- Unknown commands are rejected with a clear message

## 7. Session Security

- One active session per chat (lock to prevent concurrent prompts)
- Session state machine prevents dispatching to busy sessions
- Stale sessions are automatically archived after `SESSION_TIMEOUT_SEC`
- Session bindings are explicit and persisted

## 8. Network Security

- Webhook endpoint is a single POST route
- Health/ready endpoints expose no sensitive data
- Metrics endpoint exposes only operational metrics (no secrets, no prompts)
- TLS recommended for production (reverse proxy or Tailscale Funnel)

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Unauthorized access | Allowlist + rate limiting |
| Prompt injection | Input validation, no direct shell |
| Session hijacking | Per-chat session binding |
| Data leak | Log sanitization |
| DOS | Rate limiting, connection timeouts |
| Runtime compromise | Sandboxed workspace directories |
