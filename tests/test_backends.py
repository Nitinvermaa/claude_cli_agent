"""Tests for backend registry and credential resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from claude_cli_agent.backends.registry import (
    BACKEND_IDS,
    create_backend,
    ensure_backend_available,
    normalize_backend_id,
)
from claude_cli_agent.config import (
    AgentConfig,
    _config_has_required_credentials,
    _github_token_from_env,
    backend_needs_github_token,
    resolve_github_token,
)
from claude_cli_agent.host_tools import run_host_tool, safe_workspace_path


def test_normalize_backend_id_defaults_unknown() -> None:
    assert normalize_backend_id("bogus") == "independent"
    assert normalize_backend_id("copilot_sdk") == "copilot_sdk"


def test_backend_ids_include_copilot() -> None:
    assert "copilot_sdk" in BACKEND_IDS
    assert "langchain_copilot" in BACKEND_IDS


def test_create_builtin_backends() -> None:
    ind = create_backend("independent")
    assert ind.id == "independent"
    cc = create_backend("claude_code")
    assert cc.id == "claude_code"


def test_ensure_copilot_sdk_requires_package() -> None:
    try:
        ensure_backend_available("copilot_sdk")
    except RuntimeError as exc:
        assert "copilot" in str(exc).lower() or "Install" in str(exc)


def test_github_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    assert _github_token_from_env({}) == "ghp_test"


def test_config_credentials_copilot_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    cfg = AgentConfig(api_key="", backend_mode="copilot_sdk")
    assert _config_has_required_credentials(cfg, {})
    assert backend_needs_github_token("copilot_sdk")
    assert resolve_github_token(cfg, cwd=Path(".")) == "ghp_test"


def test_safe_workspace_path_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        safe_workspace_path(tmp_path, "../etc/passwd")


def test_run_host_tool_read(tmp_path: Path) -> None:
    f = tmp_path / "hello.txt"
    f.write_text("hi", encoding="utf-8")
    body, changed = run_host_tool(
        name="read_file",
        tool_input={"path": "hello.txt"},
        cwd=tmp_path,
        allow_write=False,
    )
    assert body == "hi"
    assert changed is False
