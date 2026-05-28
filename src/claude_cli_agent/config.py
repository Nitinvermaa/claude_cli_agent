"""Configuration loading and first-run onboarding."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.prompt import Confirm, Prompt

APP_DIR = Path.home() / ".config" / "cagent"
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_MODEL = "claude-sonnet-4-6"
# Default runtime: direct Anthropic API (reads ANTHROPIC_API_KEY and related env vars).
DEFAULT_BACKEND = "independent"
KEYRING_SERVICE = "cagent"
KEYRING_USERNAME = "default"
KEYRING_USERNAME_GITHUB = "github"
DEFAULT_COPILOT_MODEL = "gpt-4.1"
BACKEND_CHOICES = ("claude_code", "independent", "copilot_sdk", "langchain_copilot")
COPILOT_BACKENDS = frozenset({"copilot_sdk", "langchain_copilot"})
ANTHROPIC_BACKENDS = frozenset({"claude_code", "independent"})


@dataclass
class AgentConfig:
    """Runtime configuration for the CLI agent."""

    api_key: str = ""
    github_token: str = ""
    backend_mode: str = DEFAULT_BACKEND
    model: str = DEFAULT_MODEL
    copilot_model: str = DEFAULT_COPILOT_MODEL
    cli_path: str | None = None
    graphify_auto_update: bool = True
    graphify_query_first: bool = True
    full_access_project: bool = True
    auto_scaffold_on_app_request: bool = True
    require_change_confirmation: bool = True
    approval_workflow_mode: bool = True
    signed_approval_tokens: bool = True
    approval_token_ttl_seconds: int = 90
    enable_vision_support: bool = True
    enable_voice_support: bool = True
    enable_web_ui_plugin: bool = True
    approval_audit_path: str = str(APP_DIR / "approvals.jsonl")
    enable_reference_annotations: bool = True
    graphify_path: str = "graphify"
    mcp_config_path: str | None = None
    session_index_path: str = str(APP_DIR / "sessions.json")
    usage_log_path: str = str(APP_DIR / "usage_events.jsonl")
    usage_dashboard_path: str = str(APP_DIR / "usage_dashboard.html")
    prompt_color: str = "bright_white"
    accent_color: str = "bright_cyan"
    store_api_key_in_plaintext: bool = False
    plugins: list[str] = field(default_factory=list)
    skills: list[str] | str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AgentConfig":
        return cls(
            api_key=str(raw.get("api_key", "")).strip(),
            backend_mode=str(raw.get("backend_mode", DEFAULT_BACKEND)).strip() or DEFAULT_BACKEND,
            github_token=str(raw.get("github_token", "")).strip(),
            model=str(raw.get("model", DEFAULT_MODEL)).strip() or DEFAULT_MODEL,
            copilot_model=str(raw.get("copilot_model", DEFAULT_COPILOT_MODEL)).strip() or DEFAULT_COPILOT_MODEL,
            cli_path=raw.get("cli_path"),
            graphify_auto_update=bool(raw.get("graphify_auto_update", True)),
            graphify_query_first=bool(raw.get("graphify_query_first", True)),
            full_access_project=bool(raw.get("full_access_project", True)),
            auto_scaffold_on_app_request=bool(raw.get("auto_scaffold_on_app_request", True)),
            require_change_confirmation=bool(raw.get("require_change_confirmation", True)),
            approval_workflow_mode=bool(raw.get("approval_workflow_mode", True)),
            signed_approval_tokens=bool(raw.get("signed_approval_tokens", True)),
            approval_token_ttl_seconds=int(raw.get("approval_token_ttl_seconds", 90)),
            enable_vision_support=bool(raw.get("enable_vision_support", True)),
            enable_voice_support=bool(raw.get("enable_voice_support", True)),
            enable_web_ui_plugin=bool(raw.get("enable_web_ui_plugin", True)),
            approval_audit_path=str(raw.get("approval_audit_path", str(APP_DIR / "approvals.jsonl"))),
            enable_reference_annotations=bool(raw.get("enable_reference_annotations", True)),
            graphify_path=str(raw.get("graphify_path", "graphify")).strip() or "graphify",
            mcp_config_path=raw.get("mcp_config_path"),
            session_index_path=str(raw.get("session_index_path", str(APP_DIR / "sessions.json"))),
            usage_log_path=str(raw.get("usage_log_path", str(APP_DIR / "usage_events.jsonl"))),
            usage_dashboard_path=str(raw.get("usage_dashboard_path", str(APP_DIR / "usage_dashboard.html"))),
            prompt_color=str(raw.get("prompt_color", "bright_white")).strip() or "bright_white",
            accent_color=str(raw.get("accent_color", "bright_cyan")).strip() or "bright_cyan",
            store_api_key_in_plaintext=bool(raw.get("store_api_key_in_plaintext", False)),
            plugins=[str(v) for v in raw.get("plugins", [])],
            skills=raw.get("skills"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_key": self.api_key if self.store_api_key_in_plaintext else "",
            "backend_mode": self.backend_mode,
            "github_token": self.github_token if self.store_api_key_in_plaintext else "",
            "model": self.model,
            "copilot_model": self.copilot_model,
            "cli_path": self.cli_path,
            "graphify_auto_update": self.graphify_auto_update,
            "graphify_query_first": self.graphify_query_first,
            "full_access_project": self.full_access_project,
            "auto_scaffold_on_app_request": self.auto_scaffold_on_app_request,
            "require_change_confirmation": self.require_change_confirmation,
            "approval_workflow_mode": self.approval_workflow_mode,
            "signed_approval_tokens": self.signed_approval_tokens,
            "approval_token_ttl_seconds": self.approval_token_ttl_seconds,
            "enable_vision_support": self.enable_vision_support,
            "enable_voice_support": self.enable_voice_support,
            "enable_web_ui_plugin": self.enable_web_ui_plugin,
            "approval_audit_path": self.approval_audit_path,
            "enable_reference_annotations": self.enable_reference_annotations,
            "graphify_path": self.graphify_path,
            "mcp_config_path": self.mcp_config_path,
            "session_index_path": self.session_index_path,
            "usage_log_path": self.usage_log_path,
            "usage_dashboard_path": self.usage_dashboard_path,
            "prompt_color": self.prompt_color,
            "accent_color": self.accent_color,
            "store_api_key_in_plaintext": self.store_api_key_in_plaintext,
            "plugins": self.plugins,
            "skills": self.skills,
        }


def _save_key_to_keyring(api_key: str) -> bool:
    try:
        import keyring  # type: ignore
    except Exception:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)
        return True
    except Exception:
        return False


def _read_key_from_keyring() -> str | None:
    try:
        import keyring  # type: ignore
    except Exception:
        return None
    try:
        value = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception:
        return None
    return value.strip() if value else None


def _save_github_token_to_keyring(token: str) -> bool:
    try:
        import keyring  # type: ignore
    except Exception:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME_GITHUB, token)
        return True
    except Exception:
        return False


def _read_github_token_from_keyring() -> str | None:
    try:
        import keyring  # type: ignore
    except Exception:
        return None
    try:
        value = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME_GITHUB)
    except Exception:
        return None
    return value.strip() if value else None


def _github_token_from_env(dotenv_values: dict[str, str] | None = None) -> str:
    dotenv_values = dotenv_values or {}
    return (
        os.environ.get("COPILOT_GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or dotenv_values.get("COPILOT_GITHUB_TOKEN")
        or dotenv_values.get("GH_TOKEN")
        or dotenv_values.get("GITHUB_TOKEN")
        or ""
    ).strip()


def resolve_github_token(config: AgentConfig, *, cwd: Path | None = None) -> str:
    """Resolve GitHub PAT for Copilot backends."""
    token = (config.github_token or "").strip()
    if token:
        return token
    token = _read_github_token_from_keyring() or ""
    if token:
        return token
    dotenv_values: dict[str, str] = {}
    if cwd is not None:
        dotenv_values = _read_dotenv(cwd / ".env")
    return _github_token_from_env(dotenv_values)


def apply_github_token_to_env(token: str) -> None:
    if not token:
        return
    if not os.environ.get("GITHUB_TOKEN"):
        os.environ["GITHUB_TOKEN"] = token
    if not os.environ.get("GH_TOKEN"):
        os.environ["GH_TOKEN"] = token


def backend_needs_anthropic_key(backend_mode: str) -> bool:
    return backend_mode.strip().lower() in ANTHROPIC_BACKENDS


def backend_needs_github_token(backend_mode: str) -> bool:
    return backend_mode.strip().lower() in COPILOT_BACKENDS


def _config_has_required_credentials(cfg: AgentConfig, dotenv_values: dict[str, str]) -> bool:
    mode = (cfg.backend_mode or DEFAULT_BACKEND).strip().lower()
    if backend_needs_github_token(mode):
        if resolve_github_token(cfg, cwd=None) or _github_token_from_env(dotenv_values):
            return True
    if backend_needs_anthropic_key(mode):
        if (cfg.api_key or "").strip() or _read_key_from_keyring():
            return True
        env_key = (
            os.environ.get("CAGENT_ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("CLAUDE_API_KEY")
            or dotenv_values.get("CAGENT_ANTHROPIC_API_KEY")
            or dotenv_values.get("ANTHROPIC_API_KEY")
            or dotenv_values.get("CLAUDE_API_KEY")
        )
        return bool(env_key)
    return bool((cfg.api_key or "").strip())


def _write_config(config: AgentConfig) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        # Best effort on non-POSIX filesystems.
        pass


def _read_config() -> AgentConfig | None:
    if not CONFIG_PATH.exists():
        return None
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    cfg = AgentConfig.from_dict(raw)
    if not cfg.api_key:
        cfg.api_key = _read_key_from_keyring() or ""
    if not cfg.github_token:
        cfg.github_token = _read_github_token_from_keyring() or ""
    dotenv_values = _read_dotenv(Path.cwd() / ".env")
    return cfg if _config_has_required_credentials(cfg, dotenv_values) else None


def _read_dotenv(dotenv_path: Path) -> dict[str, str]:
    if not dotenv_path.exists():
        return {}
    values: dict[str, str] = {}
    try:
        raw = dotenv_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    for line in raw.splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            values[key] = value
    return values


def _usage_paths_for_cwd(cwd: Path | None) -> tuple[str, str]:
    if cwd is None:
        return str(APP_DIR / "usage_events.jsonl"), str(APP_DIR / "usage_dashboard.html")
    resolved = cwd.resolve()
    return str(resolved / "cagent-usage-events.jsonl"), str(resolved / "cagent-usage-dashboard.html")


def load_or_init_config(
    console: Console,
    api_key_override: str | None = None,
    github_token_override: str | None = None,
    backend_override: str | None = None,
    cwd: Path | None = None,
) -> AgentConfig:
    """Load config from disk/env, or prompt user for first-run setup."""
    dotenv_values: dict[str, str] = {}
    if cwd is not None:
        dotenv_values = _read_dotenv(cwd / ".env")
    usage_log_path, usage_dashboard_path = _usage_paths_for_cwd(cwd)

    model_override = (
        os.environ.get("CAGENT_MODEL")
        or os.environ.get("ANTHROPIC_MODEL")
        or os.environ.get("CLAUDE_MODEL")
        or dotenv_values.get("CAGENT_MODEL")
        or dotenv_values.get("ANTHROPIC_MODEL")
        or dotenv_values.get("CLAUDE_MODEL")
    )

    if github_token_override:
        cfg = _read_config() or AgentConfig()
        cfg.github_token = github_token_override.strip()
        if not cfg.usage_log_path:
            cfg.usage_log_path = usage_log_path
        if not cfg.usage_dashboard_path:
            cfg.usage_dashboard_path = usage_dashboard_path
        if model_override:
            cfg.model = model_override
        if backend_override:
            cfg.backend_mode = backend_override
        _save_github_token_to_keyring(github_token_override)
        apply_github_token_to_env(github_token_override)
        _write_config(cfg)
        return cfg

    if api_key_override:
        cfg = _read_config() or AgentConfig(api_key=api_key_override)
        cfg.api_key = api_key_override
        if not cfg.usage_log_path:
            cfg.usage_log_path = usage_log_path
        if not cfg.usage_dashboard_path:
            cfg.usage_dashboard_path = usage_dashboard_path
        if model_override:
            cfg.model = model_override
        if backend_override:
            cfg.backend_mode = backend_override
        _save_key_to_keyring(api_key_override)
        _write_config(cfg)
        return cfg

    env_key = (
        os.environ.get("CAGENT_ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("CLAUDE_API_KEY")
        or dotenv_values.get("CAGENT_ANTHROPIC_API_KEY")
        or dotenv_values.get("ANTHROPIC_API_KEY")
        or dotenv_values.get("CLAUDE_API_KEY")
    )
    if env_key:
        cfg = _read_config() or AgentConfig(api_key=env_key)
        cfg.api_key = env_key
        if not cfg.usage_log_path:
            cfg.usage_log_path = usage_log_path
        if not cfg.usage_dashboard_path:
            cfg.usage_dashboard_path = usage_dashboard_path
        if model_override:
            cfg.model = model_override
        if backend_override:
            cfg.backend_mode = backend_override
        _save_key_to_keyring(env_key)
        _write_config(cfg)
        return cfg

    env_github = _github_token_from_env(dotenv_values)
    if env_github:
        cfg = _read_config() or AgentConfig()
        cfg.github_token = env_github
        if not cfg.usage_log_path:
            cfg.usage_log_path = usage_log_path
        if not cfg.usage_dashboard_path:
            cfg.usage_dashboard_path = usage_dashboard_path
        if model_override:
            cfg.model = model_override
        if backend_override:
            cfg.backend_mode = backend_override
        _save_github_token_to_keyring(env_github)
        _write_config(cfg)
        return cfg

    cfg = _read_config()
    if cfg:
        if not cfg.github_token:
            cfg.github_token = _read_github_token_from_keyring() or _github_token_from_env(dotenv_values)
        if not cfg.usage_log_path:
            cfg.usage_log_path = usage_log_path
        if not cfg.usage_dashboard_path:
            cfg.usage_dashboard_path = usage_dashboard_path
        if model_override:
            cfg.model = model_override
        if backend_override:
            cfg.backend_mode = backend_override
        _write_config(cfg)
        return cfg

    console.print("[bold cyan]Welcome to cagent[/bold cyan]")
    console.print("First run setup is required.")

    backend_mode = backend_override or Prompt.ask(
        "Backend mode (default: independent = Anthropic API via ANTHROPIC_API_KEY)",
        choices=list(BACKEND_CHOICES),
        default=DEFAULT_BACKEND,
    )
    backend_mode = backend_mode.strip().lower()

    key = ""
    github_token = ""
    if backend_needs_github_token(backend_mode):
        github_token = Prompt.ask("Enter GitHub PAT (Copilot)", password=True).strip()
        while not github_token:
            github_token = Prompt.ask(
                "GitHub token cannot be empty. Enter GitHub PAT",
                password=True,
            ).strip()
    if backend_needs_anthropic_key(backend_mode):
        key = Prompt.ask("Enter Anthropic API key", password=True).strip()
        while not key:
            key = Prompt.ask("API key cannot be empty. Enter Anthropic API key", password=True).strip()

    model_default = model_override or DEFAULT_MODEL
    if backend_mode in COPILOT_BACKENDS:
        model_default = DEFAULT_COPILOT_MODEL
    model = Prompt.ask("Default model", default=model_default).strip() or model_default
    copilot_model = DEFAULT_COPILOT_MODEL
    if backend_mode in COPILOT_BACKENDS:
        copilot_model = (
            Prompt.ask("Copilot model", default=DEFAULT_COPILOT_MODEL).strip() or DEFAULT_COPILOT_MODEL
        )
    graphify_auto = Confirm.ask("Enable automatic graphify context updates?", default=True)
    graphify_query_first = Confirm.ask("Use graphify query-first context mode?", default=True)
    full_access_project = Confirm.ask(
        "Allow full write/edit/delete access in the project workspace (recommended for local coding)?",
        default=True,
    )
    auto_scaffold = Confirm.ask(
        "Auto-scaffold project files when user asks to build an app?",
        default=True,
    )
    require_change_confirmation = Confirm.ask(
        "Require explicit confirmation before implementation/mutations/push actions?",
        default=True,
    )
    approval_workflow_mode = Confirm.ask(
        "Enable strict approval workflow mode (once/task/session grants)?",
        default=True,
    )
    signed_tokens = Confirm.ask(
        "Require signed approval tokens per approval gate?",
        default=True,
    )
    enable_vision_support = Confirm.ask("Enable vision workflow support?", default=True)
    enable_voice_support = Confirm.ask("Enable voice API/app scaffolding support?", default=True)
    enable_web_ui_plugin = Confirm.ask(
        "Enable built-in web UI plugin/scaffolder (React/Vue/Next/etc.) by default?",
        default=True,
    )
    enable_reference_annotations = Confirm.ask(
        "Enable @file/@dir/@glob reference annotations in prompts?",
        default=True,
    )
    plain_store = Confirm.ask(
        "Store API key in plaintext config file? (not recommended; keyring preferred)",
        default=False,
    )
    config = AgentConfig(
        api_key=key,
        github_token=github_token,
        backend_mode=backend_mode,
        model=model,
        copilot_model=copilot_model,
        graphify_auto_update=graphify_auto,
        graphify_query_first=graphify_query_first,
        full_access_project=full_access_project,
        auto_scaffold_on_app_request=auto_scaffold,
        require_change_confirmation=require_change_confirmation,
        approval_workflow_mode=approval_workflow_mode,
        signed_approval_tokens=signed_tokens,
        approval_token_ttl_seconds=90,
        enable_vision_support=enable_vision_support,
        enable_voice_support=enable_voice_support,
        enable_web_ui_plugin=enable_web_ui_plugin,
        enable_reference_annotations=enable_reference_annotations,
        usage_log_path=usage_log_path,
        usage_dashboard_path=usage_dashboard_path,
        prompt_color="bright_white",
        accent_color="bright_cyan",
        store_api_key_in_plaintext=plain_store,
    )
    if key:
        saved_in_keyring = _save_key_to_keyring(key)
        if saved_in_keyring and not plain_store:
            console.print("[green]Anthropic API key stored in system keyring.[/green]")
        elif not plain_store and backend_needs_anthropic_key(backend_mode):
            console.print(
                "[yellow]Keyring not available; Anthropic key not persisted in plaintext. "
                "Set ANTHROPIC_API_KEY before launching.[/yellow]"
            )
    if github_token:
        if _save_github_token_to_keyring(github_token):
            console.print("[green]GitHub token stored in system keyring.[/green]")
        apply_github_token_to_env(github_token)
    _write_config(config)
    console.print(f"[green]Saved config:[/green] {CONFIG_PATH}")
    return config


def persist_config(config: AgentConfig) -> None:
    """Persist config safely and refresh keyring when possible."""
    if config.api_key:
        _save_key_to_keyring(config.api_key)
    if config.github_token:
        _save_github_token_to_keyring(config.github_token)
    _write_config(config)
