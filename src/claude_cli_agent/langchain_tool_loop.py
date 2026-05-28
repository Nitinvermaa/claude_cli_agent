"""LangChain tool loop using host workspace tools."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .host_tools import run_host_tool, workspace_tool_definitions


def _max_tool_rounds() -> int:
    raw = (os.environ.get("CAGENT_INDEPENDENT_MAX_TOOL_ROUNDS") or "").strip()
    if not raw:
        return 128
    try:
        n = int(raw, 10)
    except ValueError:
        return 128
    return max(8, min(n, 512))


def _openai_style_tools(*, allow_write: bool) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in workspace_tool_definitions(allow_write=allow_write)
    ]


def run_langchain_tool_loop(
    llm: Any,
    *,
    system: str,
    messages: list[dict[str, Any]],
    cwd: Path,
    allow_write: bool,
) -> tuple[str, int, int, str | None, bool]:
    """
    Run a LangChain chat model with host tools; mutates ``messages``.

    Returns (final_text, input_tokens, output_tokens, error, changed_files).
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    max_rounds = _max_tool_rounds()
    changed_files = False
    approx_chars = len(system) + sum(len(str(m.get("content", ""))) for m in messages)
    total_in = max(1, approx_chars // 4)
    total_out = 0

    lc_messages: list[Any] = [SystemMessage(content=system)]
    for item in messages:
        role = item.get("role")
        content = item.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=str(content)))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=str(content)))

    tool_defs = workspace_tool_definitions(allow_write=allow_write)
    tool_names = {t["name"] for t in tool_defs}

    try:
        bound = llm.bind_tools(_openai_style_tools(allow_write=allow_write))
    except Exception:
        bound = llm

    last_text = ""

    for _ in range(max_rounds):
        try:
            ai_msg = bound.invoke(lc_messages)
        except Exception as exc:
            err = str(exc)
            msg = f"LangChain Copilot backend request failed: {err}"
            messages.append({"role": "assistant", "content": msg})
            return msg, total_in, total_out, err, changed_files

        if not isinstance(ai_msg, AIMessage):
            last_text = str(getattr(ai_msg, "content", ai_msg))
            messages.append({"role": "assistant", "content": last_text})
            total_out += max(1, len(last_text) // 4)
            break

        content = ai_msg.content
        if isinstance(content, list):
            text_parts = [
                p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
            ]
            last_text = "\n".join(str(x) for x in text_parts if x).strip()
        else:
            last_text = str(content or "").strip()

        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        lc_messages.append(ai_msg)

        if not tool_calls:
            if not last_text:
                last_text = "(no text response)"
            messages.append({"role": "assistant", "content": last_text})
            total_out += max(1, len(last_text) // 4)
            break

        messages.append({"role": "assistant", "content": last_text or "(tool call)"})

        for tc in tool_calls:
            tname = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            tid = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "")
            raw_args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
            if not isinstance(raw_args, dict):
                raw_args = {}
            if str(tname) not in tool_names:
                body = f"ERROR: unknown tool {tname!r}"
            else:
                body, did_write = run_host_tool(
                    name=str(tname),
                    tool_input=raw_args,
                    cwd=cwd,
                    allow_write=allow_write,
                )
                if did_write:
                    changed_files = True
            lc_messages.append(ToolMessage(content=body, tool_call_id=str(tid or tname)))
        continue
    else:
        hint = (
            f"Stopped after {max_rounds} tool rounds (LangChain backend limit). "
            "Raise `CAGENT_INDEPENDENT_MAX_TOOL_ROUNDS` or narrow scope."
        )
        messages.append({"role": "assistant", "content": hint})
        return hint, total_in, total_out, "tool_round_limit", changed_files

    return last_text, total_in, total_out, None, changed_files
