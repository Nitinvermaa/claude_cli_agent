from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from claude_cli_agent.legacy_scripts.cli_formatting import (
    OutputChunk,
    format_for_terminal,
    split_output_chunks,
)

__all__ = ["OutputChunk", "format_for_terminal", "split_output_chunks"]
