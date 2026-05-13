import asyncio
import os
import sys
import textwrap
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    query,
)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

_ROOT = Path(__file__).resolve().parent


class ClaudeCodeLoginRequired(Exception):
    """The Claude Code CLI is not logged in; see error text for fix steps."""


def _claude_code_login_help() -> str:
    return textwrap.dedent(
        """\
        Claude Code CLI is not authenticated (this is separate from ANTHROPIC_API_KEY).
        Do this once in a terminal:
          - Install / setup: https://docs.anthropic.com/en/docs/claude-code
          - Sign in:  claude login
        """
    ).strip()


def _assistant_text(message: AssistantMessage) -> str:
    parts: list[str] = []
    thinking: list[str] = []
    for block in message.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
        elif isinstance(block, ThinkingBlock):
            thinking.append(block.thinking)
    if parts:
        return "".join(parts)
    return "\n".join(thinking) if thinking else ""


async def ask(prompt: str, options: ClaudeAgentOptions | None = None) -> None:
    chunks: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            text = _assistant_text(message)
            if message.error == "authentication_failed":
                raise ClaudeCodeLoginRequired(_claude_code_login_help())
            if text:
                chunks.append(text)
        elif isinstance(message, ResultMessage):
            if message.is_error:
                raise RuntimeError(str(message.result or message.errors or "Unknown agent error"))
            break
    if chunks:
        print("\n\n".join(chunks))


def main() -> None:
    env_path = _ROOT / ".env"
    if load_dotenv:
        load_dotenv(env_path)
    api_key = os.environ.get("CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(f"CLAUDE_API_KEY/ANTHROPIC_API_KEY not found. Set it in {env_path}")

    options = ClaudeAgentOptions(
        env={"ANTHROPIC_API_KEY": api_key},
        permission_mode="dontAsk",
    )
    sample = "Generate sample code for a basic RAG app"
    print("Claude response:\n")
    asyncio.run(ask(sample, options=options))


if __name__ == "__main__":
    try:
        main()
    except ClaudeCodeLoginRequired as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
