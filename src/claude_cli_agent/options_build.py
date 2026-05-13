"""Build ClaudeAgentOptions for each host mode."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import AgentDefinition, SdkPluginConfig

from .config import AgentConfig

AgentMode = Literal["agent", "plan", "ask", "debug"]

READ_ONLY_DISALLOWED_TOOLS = [
    "Write",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
    "Bash",
    "Task",
]


def _build_plugins(paths: list[str]) -> list[SdkPluginConfig]:
    return [{"type": "local", "path": str(Path(p).expanduser())} for p in paths if p.strip()]


def build_options(
    *,
    config: AgentConfig,
    cwd: Path,
    mode: AgentMode,
    resume_session_id: str | None = None,
    agents: dict[str, AgentDefinition] | None = None,
    full_access_override: bool = False,
) -> ClaudeAgentOptions:
    """Translate host policy into SDK options."""
    env = {
        "ANTHROPIC_API_KEY": config.api_key,
    }

    permission_mode = "default"
    disallowed_tools: list[str] = []
    include_partial_messages = False
    extra_args: dict[str, str | None] = {}

    full_access_enabled = config.full_access_project or full_access_override

    if not full_access_enabled:
        # Safe default: always Ask-style behavior when full access is disabled.
        permission_mode = "default"
        disallowed_tools = list(READ_ONLY_DISALLOWED_TOOLS)
    elif mode == "agent":
        # In some Claude environments, dontAsk can hard-deny all tool execution.
        # Use default mode with no disallowed tools for practical full-access runs.
        permission_mode = "default"
        disallowed_tools = []
    elif mode == "plan":
        permission_mode = "plan"
    elif mode == "ask":
        permission_mode = "default"
        disallowed_tools = list(READ_ONLY_DISALLOWED_TOOLS)
    elif mode == "debug":
        include_partial_messages = True
        extra_args = {"debug-to-stderr": None}
        permission_mode = "default"

    confirmation_policy = (
        "Ask user confirmation before major implementation, file mutations, git commit, or push."
        if config.require_change_confirmation
        else "User already granted implementation authority for this session; execute directly."
    )
    system_append = (
        "You are cagent, a production coding assistant. "
        "Use concise explanations, optimize context cost by preferring graph context "
        "from graphify-out/ when available, and when the user asks to build or modify an app, "
        "perform real file operations in the project (create/update/delete files) instead of only "
        "providing code snippets. Do not stop to ask for architecture confirmation if the user "
        "explicitly asked to proceed; implement end-to-end and then report what changed. "
        f"{confirmation_policy}"
    )

    options = ClaudeAgentOptions(
        tools={"type": "preset", "preset": "claude_code"},
        system_prompt={"type": "preset", "preset": "claude_code", "append": system_append},
        cwd=str(cwd),
        cli_path=config.cli_path,
        model=config.model,
        env=env,
        permission_mode=permission_mode,
        disallowed_tools=disallowed_tools,
        include_partial_messages=include_partial_messages,
        extra_args=extra_args,
        hooks=None,
        plugins=_build_plugins(config.plugins),
        skills=config.skills if config.skills else None,
        agents=agents,
        mcp_servers=str(Path(config.mcp_config_path).expanduser()) if config.mcp_config_path else {},
        resume=resume_session_id,
    )
    return options
