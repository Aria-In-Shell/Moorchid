"""Centralized configuration for the Moorchid journal application."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_FILE = "soulcontext_journal.db"
DEFAULT_SQLITE_PATH = PROJECT_ROOT / DEFAULT_SQLITE_FILE
DEFAULT_CHROMA_DIR = PROJECT_ROOT / "chroma_db"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 15.0
DEFAULT_LLM_MODEL = "deepseek-chat"
DEFAULT_EMBEDDING_MODEL = "embedding-2"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
ZHIPUAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"


def _read_env_file(path: Path) -> str | None:
    """Read ``.env`` with encodings that Windows Notepad actually writes."""
    if not path.exists():
        return None
    for encoding in ("utf-8-sig", "utf-8", "utf-16"):
        try:
            return path.read_text(encoding=encoding)
        except (OSError, UnicodeDecodeError, UnicodeError):
            continue
    return None


def _load_dotenv(path: Path, *, override: bool = True) -> None:
    """Load ``.env`` into ``os.environ``.

    ``override=True`` is required on Windows: an empty user-level
    ``DEEPSEEK_API_KEY`` would otherwise win over the file via setdefault.
    """
    raw = _read_env_file(path)
    if raw is None:
        return
    for raw_line in raw.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value


_load_dotenv(PROJECT_ROOT / ".env")


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Strongly-typed runtime configuration loaded from environment variables."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        source: Mapping[str, str] = env if env is not None else os.environ

        self.deepseek_api_key: str | None = self._clean(source.get("DEEPSEEK_API_KEY")) or None
        self.deepseek_base_url: str = self._clean(source.get("DEEPSEEK_BASE_URL")) or DEEPSEEK_BASE_URL
        self.deepseek_model: str = self._clean(source.get("DEEPSEEK_MODEL")) or DEFAULT_LLM_MODEL
        self.deepseek_timeout_seconds: float = self._float(
            source.get("DEEPSEEK_TIMEOUT_SECONDS"), DEFAULT_REQUEST_TIMEOUT_SECONDS
        )
        # A placeholder from .env.example must not count as "configured".
        if self.deepseek_api_key in {"sk-your-key-here", "sk-xxxxxxxxxxxxxxxxxxxxxxxx"}:
            self.deepseek_api_key = None
        self.deepseek_enabled: bool = bool(self.deepseek_api_key)

        self.zhipuai_api_key: str | None = self._clean(source.get("ZHIPUAI_API_KEY"))
        self.zhipuai_base_url: str = self._clean(source.get("ZHIPUAI_BASE_URL")) or ZHIPUAI_BASE_URL
        self.zhipuai_model: str = self._clean(source.get("ZHIPUAI_EMBEDDING_MODEL")) or DEFAULT_EMBEDDING_MODEL
        self.zhipuai_timeout_seconds: float = self._float(
            source.get("ZHIPUAI_TIMEOUT_SECONDS"), DEFAULT_REQUEST_TIMEOUT_SECONDS
        )
        self.zhipuai_enabled: bool = bool(self.zhipuai_api_key)

        self.vector_store_type: str = (self._clean(source.get("VECTOR_STORE_TYPE")) or "chroma").lower()
        chroma_dir = self._clean(source.get("CHROMA_PERSIST_DIR"))
        self.chroma_persist_dir: Path = (
            Path(chroma_dir).expanduser().resolve() if chroma_dir else DEFAULT_CHROMA_DIR
        )
        self.vector_collection_name: str = (
            self._clean(source.get("VECTOR_COLLECTION_NAME")) or "soulcontext_memories"
        )
        self.vector_dimension: int = self._int(source.get("VECTOR_DIMENSION"), 1024)
        self.vector_top_k: int = self._int(source.get("VECTOR_TOP_K"), 5)

        self.allow_demo_fallback: bool = _truthy(source.get("ALLOW_DEMO_FALLBACK")) or True

        self.database_path: Path = self._resolve_database_path(source.get("DATABASE_URL"))

        # ── Auth ──────────────────────────────────────────────────────────────
        # Accept both JWT_SECRET_KEY (canonical) and JWT_SECRET (legacy alias).
        jwt_secret = (
            self._clean(source.get("JWT_SECRET_KEY"))
            or self._clean(source.get("JWT_SECRET"))
        )
        if not jwt_secret:
            raise ValueError(
                "JWT_SECRET_KEY environment variable is required. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        self.jwt_secret: str = jwt_secret
        self.jwt_algorithm: str = self._clean(source.get("JWT_ALGORITHM")) or "HS256"
        self.jwt_expire_minutes: int = self._int(source.get("JWT_EXPIRE_MINUTES"), 60 * 24 * 7)  # 7 days

        # ── CORS ───────────────────────────────────────────────────────────────
        self.environment: str = self._clean(source.get("ENVIRONMENT")) or "development"
        raw_cors = source.get("CORS_ALLOWED_ORIGINS", "").strip()
        if raw_cors:
            self.cors_allowed_origins: list[str] = [
                o.strip() for o in raw_cors.split(",") if o.strip()
            ]
        elif self.environment == "production":
            self.cors_allowed_origins = []
        else:
            # Development fallback: allow the public dev host + a wildcard
            # so any LAN IP (e.g. phone on 192.168.x.x) can hit the API
            # from its own origin. The wildcard is fine here because this
            # branch only runs in non-production.
            #
            # NOTE: `allow_origins=["*"]` is incompatible with
            # `allow_credentials=True` in Starlette, so we keep the
            # explicit `42.194.168.71:3000` and `localhost:*` entries for
            # credentialed calls, then auto-extend with a wildcard list at
            # middleware registration time (see main.py).
            self.cors_allowed_origins = [
                "http://localhost:3000",
                "http://localhost:5173",
                "http://localhost:5174",
                "http://localhost:4173",
                "http://localhost:8501",
                "http://42.194.168.71:3000",
                "http://42.194.168.71:5173",
                "http://42.194.168.71:4173",
                "http://cloverspace.cn",
                "https://cloverspace.cn",
                "http://42.194.168.71",
                "*",
            ]

    @staticmethod
    def _clean(value: str | None) -> str:
        if value is None:
            return ""
        return value.strip()

    @staticmethod
    def _float(value: str | None, default: float) -> float:
        if value is None:
            return default
        try:
            parsed = float(value.strip())
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    @staticmethod
    def _int(value: str | None, default: int) -> int:
        if value is None:
            return default
        try:
            parsed = int(value.strip())
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    def _resolve_database_path(self, raw_url: str | None) -> Path:
        if not raw_url:
            return DEFAULT_SQLITE_PATH

        cleaned = raw_url.strip()
        if not cleaned:
            return DEFAULT_SQLITE_PATH

        if Path(cleaned).is_absolute():
            return Path(cleaned).resolve()

        parsed = urlparse(cleaned)
        if parsed.scheme not in {"", "sqlite", "sqlite+pysqlite", "sqlite3"}:
            raise ValueError(
                f"unsupported DATABASE_URL scheme: {parsed.scheme!r}; only sqlite is supported"
            )

        path_part = (parsed.netloc + parsed.path).lstrip("/")
        if not path_part:
            raise ValueError("DATABASE_URL must point to a file path")

        return Path(path_part).expanduser().resolve()

    def as_dict(self) -> dict[str, Any]:
        return {
            "database_path": str(self.database_path),
            "deepseek": {
                "enabled": self.deepseek_enabled,
                "base_url": self.deepseek_base_url,
                "model": self.deepseek_model,
                "timeout_seconds": self.deepseek_timeout_seconds,
            },
            "zhipuai": {
                "enabled": self.zhipuai_enabled,
                "base_url": self.zhipuai_base_url,
                "model": self.zhipuai_model,
                "timeout_seconds": self.zhipuai_timeout_seconds,
            },
            "vector_store": {
                "type": self.vector_store_type,
                "persist_dir": str(self.chroma_persist_dir),
                "collection_name": self.vector_collection_name,
                "dimension": self.vector_dimension,
                "top_k": self.vector_top_k,
            },
            "allow_demo_fallback": self.allow_demo_fallback,
            "auth": {
                "jwt_algorithm": self.jwt_algorithm,
                "jwt_expire_minutes": self.jwt_expire_minutes,
            },
            "cors": {
                "allowed_origins": self.cors_allowed_origins,
            },
            "environment": self.environment,
        }


_config_instance: Config | None = None


def get_config(env: Mapping[str, str] | None = None) -> Config:
    """Return a memoized configuration singleton, optionally rebuilt for tests."""
    global _config_instance
    if env is not None or _config_instance is None:
        _config_instance = Config(env)
    return _config_instance


def reset_config() -> None:
    """Drop the cached configuration so the next call reads the environment again."""
    global _config_instance
    _config_instance = None
