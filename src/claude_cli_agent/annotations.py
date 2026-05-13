"""Prompt annotation expansion for @file/@dir/@glob style references."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

ANNOTATION_RE = re.compile(r"(?<!\S)@([^\s]+)")
LINE_RANGE_RE = re.compile(r"^(?P<path>[^#]+)#L(?P<start>\d+)-(?P<end>\d+)$")


@dataclass
class AnnotationExpansion:
    prompt: str
    matched: list[str]
    unresolved: list[str]
    suggestions: dict[str, list[str]]
    added_chars: int


def expand_prompt_annotations(
    *,
    prompt: str,
    cwd: Path,
    max_total_chars: int = 8000,
) -> AnnotationExpansion:
    """Resolve annotation references and prepend compact context."""
    matches = ANNOTATION_RE.findall(prompt)
    if not matches:
        return AnnotationExpansion(
            prompt=prompt,
            matched=[],
            unresolved=[],
            suggestions={},
            added_chars=0,
        )

    blocks: list[str] = []
    used = 0
    matched: list[str] = []
    unresolved: list[str] = []
    suggestions: dict[str, list[str]] = {}
    cwd_resolved = cwd.resolve()

    for token in matches:
        content = _resolve_token(token, cwd_resolved, budget=max_total_chars - used)
        if not content:
            unresolved.append(token)
            suggestions[token] = suggest_annotation_candidates(token, cwd_resolved)
            continue
        matched.append(token)
        blocks.append(content)
        used += len(content)
        if used >= max_total_chars:
            break

    if not blocks:
        return AnnotationExpansion(
            prompt=prompt,
            matched=[],
            unresolved=unresolved,
            suggestions=suggestions,
            added_chars=0,
        )

    context = (
        "[Resolved reference annotations]\n"
        "The following references were expanded from @ annotations in the user prompt.\n\n"
        + "\n\n".join(blocks)
    )
    final_prompt = f"{context}\n\n[User prompt]\n{prompt}"
    return AnnotationExpansion(
        prompt=final_prompt,
        matched=matched,
        unresolved=unresolved,
        suggestions=suggestions,
        added_chars=len(context),
    )


def suggest_annotation_candidates(token: str, cwd: Path, limit: int = 8) -> list[str]:
    """Suggest closest project paths for unresolved @ tokens."""
    query = token
    for prefix in ("file:", "dir:", "glob:"):
        if query.startswith(prefix):
            query = query[len(prefix) :]
    query = query.rstrip("/")
    if "#" in query:
        query = query.split("#", 1)[0]
    query_lower = query.lower()
    if not query_lower:
        return []

    candidates: list[str] = []
    scanned = 0
    max_scan = 5000
    for p in cwd.rglob("*"):
        scanned += 1
        if scanned > max_scan:
            break
        if p.name.startswith(".") and p.is_dir():
            continue
        if p.is_dir():
            rel = str(p.relative_to(cwd)) + "/"
        elif p.is_file():
            rel = str(p.relative_to(cwd))
        else:
            continue
        candidates.append(rel)

    def score(path: str) -> float:
        p = path.lower()
        if query_lower in p:
            return 1.0 + (len(query_lower) / max(len(p), 1))
        return difflib.SequenceMatcher(None, query_lower, p).ratio()

    ranked = sorted(candidates, key=score, reverse=True)
    return ranked[:limit]


def _resolve_token(token: str, cwd: Path, budget: int) -> str | None:
    if budget <= 120:
        return None
    if token.startswith("file:"):
        return _read_file_ref(token[5:], cwd, budget)
    if token.startswith("dir:"):
        return _read_dir_ref(token[4:], cwd, budget)
    if token.startswith("glob:"):
        return _read_glob_ref(token[5:], cwd, budget)
    # Default @path behavior.
    return _read_path_ref(token, cwd, budget)


def _safe_resolve(path_text: str, cwd: Path) -> Path | None:
    p = Path(path_text)
    target = (cwd / p).resolve() if not p.is_absolute() else p.resolve()
    try:
        target.relative_to(cwd)
    except ValueError:
        return None
    return target


def _read_path_ref(path_token: str, cwd: Path, budget: int) -> str | None:
    target = _safe_resolve(path_token.rstrip("/"), cwd)
    if target is None or not target.exists():
        return None
    if target.is_dir():
        return _read_dir_ref(path_token, cwd, budget)
    return _read_file_ref(path_token, cwd, budget)


def _read_file_ref(path_token: str, cwd: Path, budget: int) -> str | None:
    # Operator: @file:path#L10-40
    line_range = LINE_RANGE_RE.match(path_token)
    if line_range:
        path_text = line_range.group("path")
        start = int(line_range.group("start"))
        end = int(line_range.group("end"))
    else:
        path_text = path_token
        start = None
        end = None

    target = _safe_resolve(path_text, cwd)
    if target is None or not target.exists() or not target.is_file():
        return None
    try:
        text = target.read_text(encoding="utf-8")
    except Exception:
        return None
    lines = text.splitlines()
    if start is not None and end is not None:
        s = max(1, start)
        e = max(s, end)
        sliced = lines[s - 1 : e]
        body = "\n".join(sliced)
        heading = f"<ref type=file path={target} lines={s}-{e}>"
    else:
        max_lines = 140
        body = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            body += "\n... (truncated)"
        heading = f"<ref type=file path={target}>"
    body = body[: max(0, budget - 120)]
    return f"{heading}\n{body}\n</ref>"


def _read_dir_ref(path_token: str, cwd: Path, budget: int) -> str | None:
    path_text = path_token.rstrip("/")
    target = _safe_resolve(path_text, cwd)
    if target is None or not target.exists() or not target.is_dir():
        return None
    lines: list[str] = []
    count = 0
    for p in sorted(target.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(cwd)
        lines.append(str(rel))
        count += 1
        if count >= 120:
            lines.append("... (truncated)")
            break
    body = "\n".join(lines)[: max(0, budget - 80)]
    return f"<ref type=dir path={target}>\n{body}\n</ref>"


def _read_glob_ref(expr: str, cwd: Path, budget: int) -> str | None:
    # Operator: @glob:src/**/*.ts!**/*.test.ts
    include = expr
    exclude = ""
    if "!" in expr:
        include, exclude = expr.split("!", 1)
    include = include.strip()
    exclude = exclude.strip()
    if not include:
        return None
    paths = [p for p in cwd.glob(include) if p.is_file()]
    if exclude:
        excluded = {p.resolve() for p in cwd.glob(exclude)}
        paths = [p for p in paths if p.resolve() not in excluded]
    lines: list[str] = []
    for p in paths[:150]:
        lines.append(str(p.relative_to(cwd)))
    if len(paths) > 150:
        lines.append("... (truncated)")
    body = "\n".join(lines)[: max(0, budget - 120)]
    return f"<ref type=glob include={include} exclude={exclude or '-'}>\n{body}\n</ref>"
