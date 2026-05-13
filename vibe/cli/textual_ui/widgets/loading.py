from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
import random
from time import time
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from vibe.cli.textual_ui.constants import MistralColors
from vibe.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic
from vibe.cli.textual_ui.widgets.spinner import SpinnerMixin, SpinnerType
from vibe.cli.textual_ui.widgets.spinner_verbs import random_verb

DEFAULT_LOADING_STATUS = "Thinking"
# Frames between picking a new verb. Roughly matches Claude Code's GlimmerMessage
# pacing — about a verb-swap every couple of seconds at the 50ms frame rate.
VERB_CYCLE_FRAMES = 40


def _format_elapsed(seconds: int) -> str:
    if seconds < 60:  # noqa: PLR2004
        return f"{seconds}s"

    minutes, secs = divmod(seconds, 60)
    if minutes < 60:  # noqa: PLR2004
        return f"{minutes}m{secs}s"

    hours, mins = divmod(minutes, 60)
    return f"{hours}h{mins}m{secs}s"


class LoadingWidget(SpinnerMixin, Static):
    # Claude Code uses a tighter shimmer pulse around the brand orange instead
    # of the rainbow gradient. Keep the structural list of TARGET_COLORS so the
    # transition animation still runs but anchor it on Claude orange.
    TARGET_COLORS = (
        "#d77757",  # claude
        "#f59575",  # claudeShimmer (lighter)
        "#d77757",
        "#a05a3f",  # darker for cycle bottom
        "#d77757",
    )
    SPINNER_TYPE = SpinnerType.CLAUDE

    EASTER_EGGS: ClassVar[list[str]] = [
        "Eating a chocolatine",
        "Eating a pain au chocolat",
        "Réflexion",
        "Analyse",
        "Contemplation",
        "Synthèse",
        "Reading Proust",
        "Oui oui baguette",
        "Counting Rs in strawberry",
        "Seeding Mistral weights",
        "Vibing",
        "Sending good vibes",
        "Petting le chat",
    ]

    EASTER_EGGS_HALLOWEEN: ClassVar[list[str]] = [
        "Trick or treating",
        "Carving pumpkins",
        "Summoning spirits",
        "Brewing potions",
        "Haunting the terminal",
        "Petting le chat noir",
    ]

    EASTER_EGGS_DECEMBER: ClassVar[list[str]] = [
        "Wrapping presents",
        "Decorating the tree",
        "Drinking hot chocolate",
        "Building snowmen",
        "Writing holiday cards",
    ]

    def __init__(self, status: str | None = None, *, show_hint: bool = True) -> None:
        super().__init__(classes="loading-widget")
        self.init_spinner()
        # Track whether the caller pinned a specific status. If they didn't,
        # we rotate through the SPINNER_VERBS list to match Claude Code.
        self._status_override: str | None = status
        self.status = status or self._get_default_status()
        self.current_color_index = 0
        self._color_direction = 1
        self.transition_progress = 0
        self._verb_frame_counter = 0
        self._indicator_widget: Static | None = None
        self._status_widget: Static | None = None
        self.hint_widget: Static | None = None
        self._show_hint = show_hint
        self.start_time: float | None = None
        self._last_elapsed: int = -1
        self._paused_total: float = 0.0
        self._pause_start: float | None = None

    def _get_easter_egg(self) -> str | None:
        EASTER_EGG_PROBABILITY = 0.10
        if random.random() < EASTER_EGG_PROBABILITY:
            available_eggs = list(self.EASTER_EGGS)

            OCTOBER = 10
            HALLOWEEN_DAY = 31
            DECEMBER = 12
            now = datetime.now()
            if now.month == OCTOBER and now.day == HALLOWEEN_DAY:
                available_eggs.extend(self.EASTER_EGGS_HALLOWEEN)
            if now.month == DECEMBER:
                available_eggs.extend(self.EASTER_EGGS_DECEMBER)

            return random.choice(available_eggs)
        return None

    def _get_default_status(self) -> str:
        # Vibe easter eggs still win when they roll a hit; otherwise fall back
        # to one of Claude Code's spinner verbs (Brewing, Cogitating, ...).
        return self._get_easter_egg() or random_verb()

    def _apply_easter_egg(self, status: str) -> str:
        return self._get_easter_egg() or status

    def pause_timer(self) -> None:
        if self._pause_start is None:
            self._pause_start = time()

    def resume_timer(self) -> None:
        if self._pause_start is not None:
            self._paused_total += time() - self._pause_start
            self._pause_start = None

    def set_status(self, status: str) -> None:
        self._status_override = status
        self.status = self._apply_easter_egg(status)
        if self._status_widget:
            self._status_widget.update(self._build_status_text())

    def compose(self) -> ComposeResult:
        with Horizontal(classes="loading-container"):
            self._indicator_widget = Static(
                self._spinner.current_frame(), classes="loading-indicator"
            )
            yield self._indicator_widget

            self._status_widget = Static("", classes="loading-status")
            yield self._status_widget

            if self._show_hint:
                self.hint_widget = NoMarkupStatic(
                    "(0s Esc/Ctrl+C to interrupt)", classes="loading-hint"
                )
                yield self.hint_widget

    def on_mount(self) -> None:
        self.start_time = time()
        self._update_animation()
        self.start_spinner_timer()

    def on_resize(self) -> None:
        self.refresh_spinner()

    def _update_spinner_frame(self) -> None:
        if not self._is_spinning:
            return
        self._update_animation()

    def _next_color_index(self) -> int:
        return self.current_color_index + self._color_direction

    def _get_color_for_position(self, position: int) -> str:
        current_color = self.TARGET_COLORS[self.current_color_index]
        next_color = self.TARGET_COLORS[self._next_color_index()]
        if position < self.transition_progress:
            return next_color
        return current_color

    def _build_status_text(self) -> str:
        parts = []
        for i, char in enumerate(self.status):
            color = self._get_color_for_position(1 + i)
            parts.append(f"[{color}]{char}[/]")
        ellipsis_start = 1 + len(self.status)
        color_ellipsis = self._get_color_for_position(ellipsis_start)
        parts.append(f"[{color_ellipsis}]… [/]")
        return "".join(parts)

    def _update_animation(self) -> None:
        total_elements = 1 + len(self.status) + 1

        if self._indicator_widget:
            spinner_char = self._spinner.next_frame()
            color = self._get_color_for_position(0)
            self._indicator_widget.update(f"[{color}]{spinner_char}[/]")

        if self._status_widget:
            self._status_widget.update(self._build_status_text())

        self.transition_progress += 1
        if self.transition_progress > total_elements:
            self.current_color_index = self._next_color_index()
            if not 0 < self.current_color_index < len(self.TARGET_COLORS) - 1:
                self._color_direction *= -1
            self.transition_progress = 0

        # Swap the verb every VERB_CYCLE_FRAMES ticks unless the caller pinned
        # a status (e.g. "Compacting"). Mirrors Claude Code's verb shimmer.
        self._verb_frame_counter += 1
        if (
            self._status_override is None
            and self._verb_frame_counter >= VERB_CYCLE_FRAMES
        ):
            self._verb_frame_counter = 0
            new_verb = self._get_default_status()
            if new_verb != self.status:
                self.status = new_verb
                if self._status_widget:
                    self._status_widget.update(self._build_status_text())

        if self.hint_widget and self.start_time is not None:
            paused = self._paused_total + (
                time() - self._pause_start if self._pause_start else 0
            )
            elapsed = int(time() - self.start_time - paused)
            if elapsed != self._last_elapsed:
                self._last_elapsed = elapsed
                self.hint_widget.update(
                    f"({_format_elapsed(elapsed)} Esc/Ctrl+C to interrupt)"
                )


@contextmanager
def paused_timer(loading_widget: LoadingWidget | None) -> Iterator[None]:
    if loading_widget:
        loading_widget.pause_timer()
    try:
        yield
    finally:
        if loading_widget:
            loading_widget.resume_timer()
