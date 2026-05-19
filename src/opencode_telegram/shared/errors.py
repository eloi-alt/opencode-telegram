from __future__ import annotations


class DomainError(Exception):
    pass


class SessionNotFoundError(DomainError):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class SessionBusyError(DomainError):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session is busy: {session_id}")


class SessionLockedError(DomainError):
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session is locked: {session_id}")


class RuntimeUnavailableError(DomainError):
    def __init__(self, detail: str = "Runtime is not available") -> None:
        self.detail = detail
        super().__init__(detail)


class RuntimeTimeoutError(DomainError):
    def __init__(self, detail: str = "Runtime timed out") -> None:
        self.detail = detail
        super().__init__(detail)


class TelegramSendError(DomainError):
    def __init__(self, detail: str = "Failed to send Telegram message") -> None:
        self.detail = detail
        super().__init__(detail)


class UnauthorizedError(DomainError):
    def __init__(self, detail: str = "Unauthorized") -> None:
        self.detail = detail
        super().__init__(detail)


class ConfigError(DomainError):
    def __init__(self, detail: str = "Configuration error") -> None:
        self.detail = detail
        super().__init__(detail)


class PersistenceError(DomainError):
    def __init__(self, detail: str = "Persistence error") -> None:
        self.detail = detail
        super().__init__(detail)


class ValidationError(DomainError):
    def __init__(self, detail: str = "Validation error") -> None:
        self.detail = detail
        super().__init__(detail)


class CommandNotAllowedError(DomainError):
    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"Command not allowed: {command}")
