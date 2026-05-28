"""Direct-API (independent) backend: Anthropic tool loop for workspace file I/O."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import anthropic

from .host_tools import run_host_tool, workspace_tool_definitions


def _max_tool_rounds() -> int:
    """How many assistant↔tool turns before stopping (large repo scans need more)."""
    raw = (os.environ.get("CAGENT_INDEPENDENT_MAX_TOOL_ROUNDS") or "").strip()
    if not raw:
        return 128
    try:
        n = int(raw, 10)
    except ValueError:
        return 128
    return max(8, min(n, 512))


def _max_tokens_per_turn() -> int:
    raw = (os.environ.get("CAGENT_INDEPENDENT_MAX_TOKENS") or "").strip()
    if not raw:
        return 16384
    try:
        n = int(raw, 10)
    except ValueError:
        return 16384
    return max(1024, min(n, 65536))


def _assistant_content_tool_use_ids(content: object) -> list[str]:
    """Collect tool_use ids from an assistant message ``content`` (API-shaped dicts)."""
    if not isinstance(content, list):
        return []
    out: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use":
            continue
        tid = str(block.get("id") or "").strip()
        if tid:
            out.append(tid)
    return out


def _user_content_tool_result_ids(content: object) -> list[str]:
    if not isinstance(content, list):
        return []
    out: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_result":
            continue
        tid = str(block.get("tool_use_id") or "").strip()
        if tid:
            out.append(tid)
    return out


def repair_independent_message_history(messages: list[dict[str, Any]]) -> None:
    """Drop suffix if history contains an assistant ``tool_use`` not matched by the next user ``tool_result``."""
    while True:
        fixed = False
        n = len(messages)
        for i in range(n):
            m = messages[i]
            if m.get("role") != "assistant":
                continue
            need = set(_assistant_content_tool_use_ids(m.get("content")))
            if not need:
                continue
            if i + 1 >= n:
                del messages[i:]
                fixed = True
                break
            nxt = messages[i + 1]
            if nxt.get("role") != "user":
                del messages[i:]
                fixed = True
                break
            got = set(_user_content_tool_result_ids(nxt.get("content")))
            if got != need:
                del messages[i:]
                fixed = True
                break
        if not fixed:
            break

    # Trailing assistant that still ends with tool_use (e.g. crash mid-loop).
    while messages:
        last = messages[-1]
        if last.get("role") != "assistant":
            break
        if _assistant_content_tool_use_ids(last.get("content")):
            messages.pop()
            continue
        break


def _coerce_tool_input(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    md = getattr(raw, "model_dump", None)
    if callable(md):
        try:
            d = md()
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return {}


def _blocks_to_input(content: object) -> list[dict[str, Any]]:
    """Serialize API content blocks for the next messages.create history entry."""
    out: list[dict[str, Any]] = []
    for block in content:  # type: ignore[assignment]
        t = getattr(block, "type", None)
        if t == "text":
            out.append({"type": "text", "text": getattr(block, "text", "")})
        elif t == "tool_use":
            inp = _coerce_tool_input(getattr(block, "input", None))
            out.append(
                {
                    "type": "tool_use",
                    "id": getattr(block, "id", ""),
                    "name": getattr(block, "name", ""),
                    "input": inp,
                }
            )
        else:
            md = getattr(block, "model_dump", None)
            if callable(md):
                dumped = md()
                if isinstance(dumped, dict):
                    out.append(dumped)
    return out


def _text_from_blocks(content: object) -> str:
    parts: list[str] = []
    for block in content:  # type: ignore[assignment]
        if getattr(block, "type", None) == "text":
            txt = getattr(block, "text", None)
            if txt:
                parts.append(str(txt))
    return "\n".join(parts).strip()


def run_independent_tool_loop(
    client: anthropic.Anthropic,
    *,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    cwd: Path,
    allow_write: bool,
) -> tuple[str, int, int, str | None, bool]:
    """
    Run messages.create in a tool loop; mutates ``messages`` by appending assistant / user turns.

    Returns (final_answer_text, input_tokens, output_tokens, error, changed_files).
    """
    repair_independent_message_history(messages)
    tools = workspace_tool_definitions(allow_write=allow_write)
    max_rounds = _max_tool_rounds()
    max_tokens = _max_tokens_per_turn()
    total_in = 0
    total_out = 0
    changed_files = False
    last_text = ""

    for _ in range(max_rounds):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=messages,
            )
        except Exception as exc:
            err = str(exc)
            msg = f"Independent backend request failed: {err}"
            messages.append({"role": "assistant", "content": msg})
            return msg, total_in, total_out, err, changed_files

        usage = getattr(response, "usage", None)
        if usage is not None:
            total_in += int(getattr(usage, "input_tokens", 0) or 0)
            total_out += int(getattr(usage, "output_tokens", 0) or 0)

        messages.append({"role": "assistant", "content": _blocks_to_input(response.content)})
        stop = getattr(response, "stop_reason", None) or ""

        # Any assistant `tool_use` blocks MUST be followed by a user message with matching
        # `tool_result` blocks — even when stop_reason is `max_tokens` (truncated mid-tool).
        tool_blocks = [
            b
            for b in response.content
            if getattr(b, "type", None) == "tool_use" and getattr(b, "id", None)
        ]

        if tool_blocks:
            user_blocks: list[dict[str, Any]] = []
            for tb in tool_blocks:
                tid = str(getattr(tb, "id", "") or "").strip()
                tname = getattr(tb, "name", "") or ""
                raw_in = getattr(tb, "input", None)
                tin = _coerce_tool_input(raw_in)
                body, did_write = run_host_tool(name=tname, tool_input=tin, cwd=cwd, allow_write=allow_write)
                if did_write:
                    changed_files = True
                user_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tid,
                        "content": body,
                    }
                )
            messages.append({"role": "user", "content": user_blocks})
            continue

        if stop == "tool_use":
            # API said tool_use but we found no usable tool blocks after serialization.
            messages.pop()
            last_text = _text_from_blocks(response.content) or "(model returned tool_use without tool blocks)"
            messages.append({"role": "assistant", "content": last_text})
            break

        if stop == "max_tokens":
            last_text = _text_from_blocks(response.content) or "(truncated at max_tokens)"
            break

        last_text = _text_from_blocks(response.content) or "(no text response)"
        break
    else:
        hint = (
            f"Stopped after {max_rounds} tool rounds (independent backend limit). "
            "For whole-repo HTML reports: narrow scope (paths/modules), raise "
            "`CAGENT_INDEPENDENT_MAX_TOOL_ROUNDS` (max 512), or use `--backend claude_code`. "
            "Very large reads inflate context—prefer summaries or fewer files per turn."
        )
        messages.append({"role": "assistant", "content": hint})
        return (
            hint,
            total_in,
            total_out,
            "tool_round_limit",
            changed_files,
        )

    return last_text, total_in, total_out, None, changed_files
