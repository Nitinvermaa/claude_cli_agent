"""Host workspace tools shared by independent and LangChain backends."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def safe_workspace_path(cwd: Path, rel: str) -> Path:
    rel = (rel or "").strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in Path(rel).parts:
        raise ValueError("path must be relative to workspace and must not contain '..'")
    root = cwd.resolve()
    target = (root / rel).resolve()
    target.relative_to(root)
    return target


def workspace_tool_definitions(*, allow_write: bool) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = [
        {
            "name": "read_file",
            "description": "Read a UTF-8 text file under the workspace root.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to workspace (no leading slash, no ..)",
                    },
                },
                "required": ["path"],
            },
        },
    ]
    if allow_write:
        tools.append(
            {
                "name": "write_file",
                "description": (
                    "Create or overwrite a UTF-8 text file under the workspace. "
                    "Creates parent directories as needed. Use for real project edits."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path relative to workspace (no leading slash, no ..)",
                        },
                        "content": {"type": "string", "description": "Full new file contents"},
                    },
                    "required": ["path", "content"],
                },
            }
        )
        tools.append(
            {
                "name": "delete_path",
                "description": (
                    "Delete a file, or a directory. Empty directories can be removed without recursive. "
                    "For a non-empty directory tree, set recursive=true (destructive)."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path relative to workspace (no leading slash, no ..)",
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "If true, delete a non-empty directory tree with shutil.rmtree",
                            "default": False,
                        },
                    },
                    "required": ["path"],
                },
            }
        )
    return tools


def run_host_tool(
    *,
    name: str,
    tool_input: dict[str, Any],
    cwd: Path,
    allow_write: bool,
) -> tuple[str, bool]:
    """Returns (tool_result_text, changed_workspace_file)."""
    if name == "read_file":
        rel = str(tool_input.get("path", "")).strip()
        try:
            target = safe_workspace_path(cwd, rel)
        except ValueError as exc:
            return f"ERROR: {exc}", False
        if not target.is_file():
            return f"ERROR: not a file: {rel}", False
        try:
            return target.read_text(encoding="utf-8"), False
        except OSError as exc:
            return f"ERROR: {exc}", False

    if name == "write_file":
        if not allow_write:
            return "ERROR: write_file is disabled in this session (use agent/debug mode with full access).", False
        rel = str(tool_input.get("path", "")).strip()
        content = tool_input.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        try:
            target = safe_workspace_path(cwd, rel)
        except ValueError as exc:
            return f"ERROR: {exc}", False
        if target.exists() and target.is_dir():
            return f"ERROR: path is a directory: {rel}", False
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return f"ERROR: {exc}", False
        return f"OK: wrote {len(content)} characters to {rel}", True

    if name == "delete_path":
        if not allow_write:
            return "ERROR: delete_path is disabled in this session.", False
        rel = str(tool_input.get("path", "")).strip()
        recursive = bool(tool_input.get("recursive", False))
        try:
            target = safe_workspace_path(cwd, rel)
        except ValueError as exc:
            return f"ERROR: {exc}", False
        if not target.exists():
            return f"OK: nothing to delete at {rel}", False
        if target.is_file():
            try:
                target.unlink()
            except OSError as exc:
                return f"ERROR: {exc}", False
            return f"OK: deleted file {rel}", True
        if target.is_dir():
            if recursive:
                try:
                    shutil.rmtree(target)
                except OSError as exc:
                    return f"ERROR: {exc}", False
                return f"OK: recursively deleted directory {rel}", True
            try:
                target.rmdir()
                return f"OK: deleted empty directory {rel}", True
            except OSError:
                return (
                    "ERROR: directory not empty; pass recursive=true only if you intend to delete the entire tree.",
                    False,
                )

    return f"ERROR: unknown tool {name!r}", False
