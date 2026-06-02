from __future__ import annotations

from dataclasses import dataclass
from os import environ, getenv
from pathlib import Path


_DOTENV_LOADED = False


def _load_dotenv(path: str = ".env") -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return

    dotenv_path = Path(path)
    if not dotenv_path.exists() or not dotenv_path.is_file():
        _DOTENV_LOADED = True
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in environ:
            environ[key] = value

    _DOTENV_LOADED = True


def _read_int(name: str, default: int) -> int:
    raw_value = getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class RivalSettings:
    base_url: str = "https://haynesworld.com"
    api_base_url: str = "https://haynesworld.com"
    bot_username: str = "therival"
    bot_user_id: str | None = None
    api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    poll_interval_seconds: int = 300
    request_timeout_seconds: int = 20
    runtime_mode: str = "local"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/rival"
    admin_token: str = "dev-admin-token"
    api_bind_host: str = "127.0.0.1"
    api_bind_port: int = 8080

    @classmethod
    def from_env(cls) -> "RivalSettings":
        _load_dotenv()
        defaults = cls()
        return cls(
            base_url=getenv("HAYNESWORLD_BASE_URL", defaults.base_url),
            api_base_url=getenv("HAYNESWORLD_API_BASE_URL", defaults.api_base_url),
            bot_username=getenv("RIVAL_BOT_USERNAME", defaults.bot_username),
            bot_user_id=getenv("RIVAL_BOT_USER_ID") or None,
            api_key=getenv("RIVAL_API_KEY") or None,
            ollama_base_url=getenv("OLLAMA_BASE_URL", defaults.ollama_base_url),
            ollama_model=getenv("OLLAMA_MODEL", defaults.ollama_model),
            poll_interval_seconds=_read_int("RIVAL_POLL_INTERVAL_SECONDS", defaults.poll_interval_seconds),
            request_timeout_seconds=_read_int("RIVAL_REQUEST_TIMEOUT_SECONDS", defaults.request_timeout_seconds),
            runtime_mode=getenv("RIVAL_RUNTIME_MODE", defaults.runtime_mode),
            database_url=getenv("RIVAL_DATABASE_URL", defaults.database_url),
            admin_token=getenv("RIVAL_ADMIN_TOKEN", defaults.admin_token),
            api_bind_host=getenv("RIVAL_API_BIND_HOST", defaults.api_bind_host),
            api_bind_port=_read_int("RIVAL_API_BIND_PORT", defaults.api_bind_port),
        )