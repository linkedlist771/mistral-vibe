"""Clawd — Claude Code's terminal mascot.

Renders the 2-row block-character mascot from
``claude-code/src/components/LogoV2/Clawd.tsx``. The TUI version is static (the
real client animates pose changes — look-left, look-right, arms-up, blink — but
we render only the default pose here to keep the implementation simple).
"""
from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.widgets import Static

# Default pose (see Clawd.tsx → POSES.default)
#   r1L = " ▐"   r1E = "▛███▜"   r1R = "▌"
#   r2L = "▝▜"   middle = "    "   r2R = "▛▘"
# `clawd_body` is the orange brand color; `clawd_background` is black behind the
# eyes/forehead row. Both are applied via Rich markup, which Textual's Static
# widget renders to ANSI.
ROW_1 = "[#D77757] ▐[/][#D77757 on black]▛███▜[/][#D77757]▌[/]"
ROW_2 = "[#D77757]▝▜    ▛▘[/]"


class Clawd(Static):
    """Static mascot, two rows tall, ~8 cells wide.

    The ``animate`` flag is accepted for API parity with the older PetitChat
    widget but is ignored — pose animation is left as future work.
    """

    def __init__(self, animate: bool = True, **kwargs: Any) -> None:
        super().__init__(**kwargs, classes="banner-chat")
        self._do_animate = animate

    def compose(self) -> ComposeResult:
        yield Static(ROW_1 + "\n" + ROW_2, markup=True, classes="petit-chat")

    def on_mount(self) -> None:  # noqa: D401 — match PetitChat surface
        # No-op kept for parity with PetitChat.on_mount.
        pass

    def freeze_animation(self) -> None:
        # No-op (static mascot).
        pass
