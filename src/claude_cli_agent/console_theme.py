"""Rich Console defaults: dark-terminal-friendly text (not low-contrast gray on white)."""

from __future__ import annotations

import os

from rich.console import Console
from rich.theme import Theme

# Preset "dark": assume dark terminal background — use light foregrounds.
_THEME_DARK = Theme(
    {
        "info": "#e5e7eb",
        "warning": "#fbbf24",
        "danger": "#f87171",
        "repr.str": "#86efac",
        "repr.number": "#22d3ee",
        "repr.attrib_name": "#fde047",
        "repr.attrib_value": "#d946ef",
        "logging.level.info": "#22d3ee",
        "logging.level.warning": "#fbbf24",
        "logging.level.error": "#f87171",
    }
)

# Use only names / hex Rich can parse across versions (avoid NNN palette suffixes like cyan4).
_THEME_LIGHT = Theme(
    {
        "info": "#1f2937",
        "warning": "#b45309",
        "danger": "red",
        "repr.str": "#047857",
        "repr.number": "#0e7490",
        "repr.attrib_name": "#b45309",
        "repr.attrib_value": "#6d28d9",
        "logging.level.info": "#0e7490",
        "logging.level.warning": "#b45309",
        "logging.level.error": "red",
    }
)


def _terminal_suggests_light_background() -> bool:
    """Best-effort: light / tinted terminal backgrounds (xterm ``COLORFGBG``).

    White and light-gray are common; many macOS Terminal “Ocean” / blue-tint profiles
    use cyan–blue cube indices (e.g. 153, 195) which we must treat as light so we do
    not render ``dim`` / pale cyan (unreadable on pastel backgrounds).
    """
    raw = (os.environ.get("COLORFGBG") or "").strip()
    if ";" not in raw:
        return False
    try:
        bg = int(raw.split(";")[-1])
    except ValueError:
        return False
    # 8-color: 7 = light gray; 15 = bright white.
    if bg in (7, 15):
        return True
    # 256-color grayscale ramp: very light paper / pale gray (common “light” themes).
    if bg >= 248:
        return True
    # Dark end of grayscale ramp — assume dark terminal.
    if 232 <= bg <= 243:
        return False
    # Light cyan / aqua / sky bands in the 6×6×6 cube (Terminal.app tinted profiles).
    if 110 <= bg <= 124:
        return True
    if 151 <= bg <= 159:
        return True
    if 186 <= bg <= 197:
        return True
    return False


def use_dark_ink() -> bool:
    """Use dark foreground hexes (readable on white or pastel terminal backgrounds).

    True when ``cli_theme_preset()`` is ``light``, or when ``CAGENT_USE_DARK_INK`` is set
    to ``1`` / ``true`` / ``yes`` / ``force`` (override if auto-detection misses your profile).
    """
    # Hard override: allow users to force dark UI even on light terminals.
    force_dark_ui = (os.environ.get("CAGENT_FORCE_DARK_UI") or "").strip().lower()
    if force_dark_ui in {"1", "true", "yes", "force"}:
        return False
    # Explicit light theme should always keep dark ink for readability.
    forced_theme = (os.environ.get("CAGENT_CLI_THEME") or "").strip().lower()
    if forced_theme in {"light", "white"}:
        return True
    v = (os.environ.get("CAGENT_USE_DARK_INK") or "").strip().lower()
    if v in {"1", "true", "yes", "force", "light"}:
        return True
    # Contrast safety: if terminal background appears light/tinted, keep dark ink even
    # when CAGENT_CLI_THEME was set to dark by mistake.
    if _terminal_suggests_light_background():
        return True
    return cli_theme_preset() == "light"


def cli_theme_preset() -> str:
    """UI contrast preset: light = dark ink on assumed pale terminal, dark = light ink.

    Unset ``CAGENT_CLI_THEME`` defaults to **auto**: infer light / tinted background from
    ``COLORFGBG`` when present, otherwise treat as dark terminal.

    If auto still picks wrong for your profile, set ``CAGENT_CLI_THEME=light`` or
    ``CAGENT_USE_DARK_INK=1`` (see ``use_dark_ink``).
    """
    v = (os.environ.get("CAGENT_CLI_THEME") or "auto").strip().lower()
    if v in {"light", "white"}:
        return "light"
    if v in {"dark", "black"}:
        return "dark"
    if v in {"auto", ""}:
        return "light" if _terminal_suggests_light_background() else "dark"
    return "dark"


def make_console(**kwargs: object) -> Console:
    """Rich console theme: light palette whenever we use dark ink (pastel or white terminals)."""
    theme = _THEME_LIGHT if use_dark_ink() else _THEME_DARK
    return Console(
        theme=theme,
        highlight=True,
        soft_wrap=True,
        **kwargs,  # type: ignore[arg-type]
    )
