import os
import sys
import textwrap
from pathlib import Path

import anthropic
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
_DEFAULT_MODEL = "claude-sonnet-4-6"


def _api_key() -> str:
    load_dotenv(_ROOT / ".env")
    key = os.getenv("CLAUDE_API_KEY")
    if not key:
        print(
            "No API key found. Set CLAUDE_API_KEY (or ANTHROPIC_API_KEY) in "
            f"{_ROOT / '.env'}",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def format_output_paragraphs(text: str, width: int = 88) -> str:
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if not blocks:
        blocks = [text.strip()] if text.strip() else []
    filled: list[str] = []
    for block in blocks:
        line = " ".join(s for s in (ln.strip() for ln in block.splitlines()) if s)
        if line:
            filled.append(textwrap.fill(line, width=width))
    return "\n\n".join(filled)


def chat_anthropic(
    user_text: str,
    system: str = "You are a concise assistant.",
    *,
    model: str | None = None,
) -> str:
    api_key = _api_key()
    model_name = model or os.getenv("CLAUDE_MODEL", _DEFAULT_MODEL)
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model_name,
        max_tokens=512,
        temperature=0.2,
        system=system,
        messages=[{"role": "user", "content": user_text}],
    )
    return msg.content[0].text


def main() -> None:
    print(
        format_output_paragraphs(
            chat_anthropic(
                "Explain RAG, give sample code of rag application to read, PDF, WEB using langchain and chromaDB "
            )
        )
    )


if __name__ == "__main__":
    main()
