"""Legacy compatibility wrapper for the previous standalone script."""

from __future__ import annotations

from rich.console import Console

from ..cli.main import app


def main() -> None:
    console = Console()
    console.print(
        "[yellow]Legacy script moved.[/yellow] "
        "Use `cagent` directly. Running equivalent CLI now..."
    )
    app()


if __name__ == "__main__":
    main()
