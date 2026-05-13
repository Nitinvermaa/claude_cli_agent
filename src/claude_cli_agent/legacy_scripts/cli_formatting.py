from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass


_FENCE_RE = re.compile(r"```(?P<lang>[^\n`]*)\n(?P<body>.*?)```", re.DOTALL)
_LIST_PREFIX_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+")


@dataclass
class OutputChunk:
    kind: str
    content: str
    language: str = ""


def split_output_chunks(text: str) -> list[OutputChunk]:
    chunks: list[OutputChunk] = []
    cursor = 0
    for match in _FENCE_RE.finditer(text):
        start, end = match.span()
        if start > cursor:
            prose = text[cursor:start].strip()
            if prose:
                chunks.append(OutputChunk(kind="prose", content=prose))
        language = (match.group("lang") or "").strip()
        code = match.group("body").rstrip("\n")
        if code.strip():
            chunks.append(OutputChunk(kind="code", content=code, language=language or "text"))
        cursor = end
    if cursor < len(text):
        prose = text[cursor:].strip()
        if prose:
            chunks.append(OutputChunk(kind="prose", content=prose))
    if not chunks and text.strip():
        chunks.append(OutputChunk(kind="prose", content=text.strip()))
    return chunks


def _wrap_prose_block(block: str, width: int) -> str:
    lines = [line.rstrip() for line in block.splitlines()]
    wrapped_lines: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        text = " ".join(line.strip() for line in paragraph if line.strip())
        if text:
            wrapped_lines.append(textwrap.fill(text, width=width))
        paragraph.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            if wrapped_lines and wrapped_lines[-1] != "":
                wrapped_lines.append("")
            continue
        list_match = _LIST_PREFIX_RE.match(line)
        if list_match:
            flush_paragraph()
            indent = list_match.group(1)
            marker = list_match.group(2)
            body = stripped[len(marker) :].strip()
            wrapped_lines.append(
                textwrap.fill(
                    body,
                    width=width,
                    initial_indent=f"{indent}{marker} ",
                    subsequent_indent=f"{indent}{' ' * (len(marker) + 1)}",
                )
            )
            continue
        if stripped.startswith((">", "#", "`")):
            flush_paragraph()
            wrapped_lines.append(line)
            continue
        paragraph.append(line)

    flush_paragraph()
    return "\n".join(wrapped_lines).strip()


def format_for_terminal(text: str, width: int = 100) -> str:
    rendered: list[str] = []
    for chunk in split_output_chunks(text):
        if chunk.kind == "prose":
            rendered_text = _wrap_prose_block(chunk.content, width=width)
            if rendered_text:
                rendered.append(rendered_text)
            continue
        language = chunk.language or "text"
        rendered.append(f"[code:{language}]")
        rendered.append(chunk.content)
        rendered.append("[/code]")
    return "\n\n".join(part for part in rendered if part.strip()).strip()
