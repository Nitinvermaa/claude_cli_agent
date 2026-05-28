"""Sync Claude Code project permissions when cagent grants full workspace access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Broad allow rules for the project workspace (Claude Code permission rule syntax).
_FULL_ACCESS_ALLOW = [
    "Read(**)",
    "Write(**)",
    "Edit(**)",
    "MultiEdit(**)",
    "NotebookEdit(**)",
    "Glob(**)",
    "Grep(**)",
    "Bash(**)",
    "Task",
    "Write(docs/**)",
    "Write(.claude/**)",
    "Write(.claude/settings.json)",
]


def ensure_claude_project_permissions(cwd: Path, *, full_access: bool) -> tuple[Path | None, str | None]:
    """
    Write or update ``.claude/settings.json`` under ``cwd`` (host-side, not via Claude tools).

    ``.claude/`` is a protected path in acceptEdits mode; cagent writes this file directly
    and sets ``bypassPermissions`` so approved sessions can Write/Edit/Bash without prompts.

    Returns ``(settings_path, error_message)``.
    """
    if not full_access:
        return None, None
    root = cwd.resolve()
    if not root.is_dir():
        return None, f"not a directory: {root}"

    claude_dir = root / ".claude"
    settings_path = claude_dir / "settings.json"
    existing: dict[str, Any] = {}
    if settings_path.exists():
        try:
            raw = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                existing = raw
        except (OSError, json.JSONDecodeError) as exc:
            return None, f"could not read existing settings: {exc}"

    permissions = dict(existing.get("permissions") or {})
    permissions["defaultMode"] = "bypassPermissions"
    allow = list(permissions.get("allow") or [])
    for rule in _FULL_ACCESS_ALLOW:
        if rule not in allow:
            allow.append(rule)
    permissions["allow"] = allow
    existing["permissions"] = permissions

    try:
        claude_dir.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return None, str(exc)
    return settings_path, None


def sync_claude_project_permissions(console, cwd: Path, *, full_access: bool) -> Path | None:
    """Write settings and print a user-visible status line."""
    path, err = ensure_claude_project_permissions(cwd, full_access=full_access)
    if err:
        console.print(f"[red]Could not write Claude Code permissions:[/red] {err}")
        return None
    if path:
        console.print(
            f"[green]Claude Code permissions ready:[/green] {path} "
            "(bypassPermissions — Write/Edit/Bash auto-approved in this project)"
        )
    return path
