"""REPL prompt completion: /commands and @ workspace paths (Cursor-style)."""

from __future__ import annotations

import re
from pathlib import Path

from .host_commands import COMMAND_META, HostCommandCompleter

try:
    from prompt_toolkit.completion import Completer, Completion
except Exception:  # pragma: no cover
    Completor = object  # type: ignore[assignment,misc]
    Completion = None  # type: ignore[assignment]

AT_FRAGMENT_RE = re.compile(r"(?<!\S)@([^\s]*)$")

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".idea",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        "target",
        ".tox",
        "graphify-out",
    }
)

ANNOTATION_PREFIXES: tuple[tuple[str, str], ...] = (
    ("file:", "Reference a file (optionally #L10-40)"),
    ("dir:", "List files under a directory"),
    ("glob:", "Glob pattern (optional !exclude)"),
)


def scan_workspace_paths(cwd: Path, *, max_entries: int = 4000) -> list[str]:
    """Relative file and directory paths under ``cwd`` for @ completion."""
    root = cwd.resolve()
    if not root.is_dir():
        return []

    paths: list[str] = []
    count = 0

    def add(rel: str) -> None:
        nonlocal count
        if count >= max_entries:
            return
        paths.append(rel)
        count += 1

    try:
        for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if entry.name in SKIP_DIR_NAMES:
                continue
            if entry.name.startswith(".") and entry.name not in {".env", ".env.example"}:
                continue
            if entry.is_dir():
                add(entry.name + "/")
            elif entry.is_file():
                add(entry.name)
    except OSError:
        pass

    for dirpath, _dirnames, filenames in _walk_pruned(root):
        if count >= max_entries:
            break
        rel_dir = dirpath.relative_to(root)
        dir_key = str(rel_dir).replace("\\", "/")
        if dir_key != ".":
            add(dir_key + "/")
        rel_prefix = "" if dir_key == "." else dir_key + "/"

        for name in sorted(filenames, key=str.lower):
            if count >= max_entries:
                break
            if name.startswith(".") and name not in {".env", ".env.example"}:
                continue
            add(rel_prefix + name)

    return paths


def _walk_pruned(root: Path):
    """os.walk-style traversal with pruned vendor/build directories."""
    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            names = list(current.iterdir())
        except OSError:
            continue
        dirs: list[str] = []
        files: list[str] = []
        for p in names:
            if p.name in SKIP_DIR_NAMES:
                continue
            if p.name.startswith(".") and p.name not in {".env", ".env.example"}:
                continue
            if p.is_dir():
                dirs.append(p.name)
                stack.append(p)
            elif p.is_file():
                files.append(p.name)
        yield current, dirs, files


def _at_fragment(line: str) -> tuple[str, str] | None:
    """Return (full_fragment including @, token after @) or None."""
    m = AT_FRAGMENT_RE.search(line)
    if not m:
        return None
    token = m.group(1)
    return "@" + token, token


class CagentPromptCompleter(Completer):
    """Tab completion for ``/`` host commands and ``@`` workspace references."""

    def __init__(self, *, cwd: Path, command_meta: dict[str, str] | None = None) -> None:
        self._cwd = cwd.resolve()
        self._host = HostCommandCompleter(command_meta or COMMAND_META)
        self._paths_cache: list[str] | None = None
        self._paths_for: Path | None = None

    def _workspace_paths(self) -> list[str]:
        if self._paths_cache is None or self._paths_for != self._cwd:
            self._paths_cache = scan_workspace_paths(self._cwd)
            self._paths_for = self._cwd
        return self._paths_cache

    def refresh_workspace_paths(self) -> None:
        """Invalidate path cache (e.g. after scaffold)."""
        self._paths_cache = None
        self._paths_for = None

    def get_completions(self, document, complete_event):  # type: ignore[no-untyped-def]
        if Completion is None:
            return

        line = document.text_before_cursor
        at = _at_fragment(line)
        if at is not None:
            yield from self._at_completions(fragment=at[0], token=at[1])
            return

        yield from self._host.get_completions(document, complete_event)

    def _at_completions(self, *, fragment: str, token: str):
        start_position = -len(fragment)
        mode = "any"
        query = token
        if token.startswith("file:"):
            mode = "file"
            query = token[5:]
        elif token.startswith("dir:"):
            mode = "dir"
            query = token[4:]
        elif token.startswith("glob:"):
            mode = "glob"
            query = token[5:]

        q = query.lower()
        limit = 40
        shown = 0

        if len(token) <= 5:
            for prefix, meta in ANNOTATION_PREFIXES:
                if shown >= limit:
                    break
                full = "@" + prefix
                if not token or full.lower().startswith("@" + token.lower()) or prefix.startswith(token):
                    yield Completion(full, start_position=start_position, display_meta=meta)
                    shown += 1

        for rel in self._workspace_paths():
            if shown >= limit:
                break
            if mode == "file" and rel.endswith("/"):
                continue
            if mode == "dir" and not rel.endswith("/"):
                continue
            rel_l = rel.lower()
            if q and not rel_l.startswith(q) and q not in rel_l:
                continue

            if mode == "file":
                insert = f"@file:{rel.rstrip('/')}"
            elif mode == "dir":
                insert = f"@dir:{rel.rstrip('/')}/"
            elif mode == "glob":
                insert = f"@glob:{rel.rstrip('/')}"
            else:
                insert = f"@{rel}"

            if token and not insert.lower().startswith("@" + token.lower()):
                continue

            meta = "directory" if rel.endswith("/") else "file"
            yield Completion(insert, start_position=start_position, display_meta=meta)
            shown += 1
