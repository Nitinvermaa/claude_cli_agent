"""Pluggable agent backends (Claude SDK, Anthropic API, Copilot SDK, LangChain)."""

from .base import BackendCapabilities, BackendContext, QueryResult
from ..config import DEFAULT_BACKEND
from .registry import (
    BACKEND_IDS,
    create_backend,
    ensure_backend_available,
    list_backends,
    normalize_backend_id,
)

__all__ = [
    "DEFAULT_BACKEND",
    "BACKEND_IDS",
    "BackendCapabilities",
    "BackendContext",
    "QueryResult",
    "create_backend",
    "ensure_backend_available",
    "list_backends",
    "normalize_backend_id",
]
