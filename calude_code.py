from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from claude_cli_agent.legacy_scripts.calude_code import main


if __name__ == "__main__":
    main()
