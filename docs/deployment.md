# Deployment

## Local Development

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN
export FAKE_RUNTIME=true
opencode-telegram
```

## Production with Docker

```bash
# Build and run
docker compose -f docker/docker-compose.yml up -d --build

# Check logs
docker compose -f docker/docker-compose.yml logs -f
```

## Production with Docker (standalone)

```bash
docker build -f docker/Dockerfile -t opencode-telegram .
docker run -d \
  --name opencode-telegram \
  -p 8080:8080 \
  -v opencode-data:/data \
  -v opencode-workspaces:/home/opencode/workspaces \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e OPENCODE_MODE=cli \
  -e OPENCODE_DEFAULT_WORKSPACE=my-project \
  opencode-telegram
```

## Webhook Setup

### 1. Expose the service

**Option A: Cloudflare Tunnel (easiest)**
```bash
cloudflared tunnel --url http://localhost:8080
```

**Option B: Reverse proxy with nginx + Let's Encrypt**
```nginx
server {
    listen 443 ssl;
    server_name bot.example.com;
    ssl_certificate /etc/letsencrypt/live/bot.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.example.com/privkey.pem;

    location /webhook {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Option C: Tailscale Funnel**
```bash
tailscale funnel --bg 8080
```

### 2. Set Telegram webhook

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-public-url/webhook"}'
```

### 3. Verify

```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

## Systemd Service

```ini
[Unit]
Description=OpenCode Telegram Bridge
After=network.target

[Service]
Type=simple
User=opencode
WorkingDirectory=/opt/opencode-telegram
EnvironmentFile=/opt/opencode-telegram/.env
ExecStart=/usr/local/bin/opencode-telegram
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Health Checks

```
GET /health    → {"status": "ok", "runtime": {...}, "storage": true, "active_sessions": 1}
GET /ready     → {"status": "ok"}
GET /metrics   → Prometheus-style metrics
```
