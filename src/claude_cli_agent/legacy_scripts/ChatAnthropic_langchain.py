"""Minimal LangChain + Anthropic chat using CLAUDE_API_KEY and CLAUDE_MODEL from .env."""

import os
import sys
import textwrap
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message=r".*Pydantic V1 functionality.*",
)

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

_ROOT = Path(__file__).resolve().parent
_DEFAULT_MODEL = "claude-sonnet-4-6"


def _load_config() -> tuple[str, str]:
    load_dotenv(_ROOT / ".env")
    api_key = os.getenv("CLAUDE_API_KEY")
    model = os.getenv("CLAUDE_MODEL", _DEFAULT_MODEL)
    if not api_key:
        print(
            "CLAUDE_API_KEY not found. Set it in "
            f"{_ROOT / '.env'}",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key, model


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


def main() -> None:
    api_key, model = _load_config()
    llm = ChatAnthropic(
        model=model,
        api_key=api_key,
        temperature=0.5,
    )
    messages = [HumanMessage(content="Does claude_agent_sdk require the claude CLI")]
    response = llm.invoke(messages)
    print(format_output_paragraphs(str(response.content)))


if __name__ == "__main__":
    main()
