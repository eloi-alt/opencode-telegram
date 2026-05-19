# Architecture

## Overview

OpenCode Telegram Bridge follows a clean hexagonal (ports & adapters) architecture with strict separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI HTTP Server                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │  /webhook  │  /health  │  /ready  │  /metrics     │  │
│  └────────────────────┬───────────────────────────────┘  │
│                        │                                  │
│  ┌─────────────────────▼──────────────────────────────┐  │
│  │            TelegramUpdateHandler                    │  │
│  │   (routes updates to the correct use case)         │  │
│  └──────────┬──────────────────────────┬──────────────┘  │
│             │                          │                  │
│  ┌──────────▼──────────┐  ┌───────────▼─────────────┐   │
│  │  HandleMessage      │  │  HandleCommand           │   │
│  │  UseCase            │  │  UseCase                 │   │
│  └──────────┬──────────┘  └───────────┬─────────────┘   │
│             │                          │                  │
│  ┌──────────▼──────────────────────────▼─────────────┐  │
│  │              Ports (Abstract Interfaces)          │  │
│  │  AgentRuntime │ Repository │ TelegramClient        │  │
│  └──────────┬──────────────────────────┬─────────────┘  │
│             │                          │                  │
│  ┌──────────▼──────────┐  ┌───────────▼─────────────┐   │
│  │  OpenCode Adapters  │  │  SQLite Repositories     │   │
│  │  (API/CLI/Fake)     │  │  (Session/User/Chat/...) │   │
│  └─────────────────────┘  └─────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Layers

### 1. Interface Layer (`interfaces/`)
- **FastAPI routes** (`http.py`): HTTP endpoints for webhook, health, readiness, metrics
- **Telegram handler** (`interfaces/telegram/handlers.py`): Dispatches Telegram updates to use cases

### 2. Application Layer (`app/`)
- **Use cases** (`app/usecases/`): Business logic for handling messages and commands
- **DI Container** (`app/di.py`): Wires all dependencies together

### 3. Domain Layer (`domain/`)
- **Entities**: Core business objects (User, Session, Message, Chat, etc.)
- **Value Objects**: Enums, IDs, and typed wrappers
- **Ports**: Abstract interfaces for repositories and runtime adapters

### 4. Infrastructure Layer (`infrastructure/`)
- **OpenCode adapters**: API, CLI, and Fake runtime implementations
- **Persistence**: SQLite repositories with full schema
- **Telegram**: HTTP client and message formatting
- **Config**: Pydantic-based settings with env file support
- **Security**: Authorization, rate limiting, input validation

### 5. Shared (`shared/`)
- **Errors**: Domain-specific exception hierarchy
- **Types**: Shared type aliases

## Key Design Decisions

### OpenCode Runtime Abstraction
The `OpenCodeRuntime` interface decouples Telegram from the underlying agent engine. Three implementations:
- **OpenCodeApiAdapter**: Connects to OpenCode via REST API (preferred)
- **OpenCodeCliAdapter**: Manages OpenCode as a subprocess (fallback)
- **FakeOpenCodeAdapter**: In-memory mock for development and testing

### Persistence
SQLite via aiosqlite, abstracted behind repository interfaces. Full schema with indexes, WAL mode, and foreign keys. All I/O is async.

### Session State Machine
```
pending ──► starting ──► ready ──► busy ──► streaming ──► idle
                           │         │                      │
                           │         ▼                      │
                           │      failed                    │
                           │         │                      │
                           ▼         ▼                      ▼
                         stopped ◄───────────────────── archived
```

### Security Model
- Optional allowlists for users and chats
- Rate limiting per key
- Admin command protection
- Dangerous command blocklist
- Input validation at all boundaries
