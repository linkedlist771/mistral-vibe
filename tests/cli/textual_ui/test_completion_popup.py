from __future__ import annotations

from vibe.cli.textual_ui.widgets.chat_input.completion_popup import CompletionPopup


# Each `@`-prefixed label gets a `+ ` glyph (Claude Code parity); each `/`-prefixed
# label gets a `* ` glyph. Both consume 2 extra terminal cells.
GLYPH_WIDTH = 2


def test_rendered_text_length_uses_terminal_cell_width() -> None:
    # "你" and "🙂" both occupy 2 terminal cells in Rich (+2 for separator
    # +2 for the file glyph "+ ").
    assert CompletionPopup.rendered_text_length("@你", "🙂") == 6 + GLYPH_WIDTH


def test_rendered_text_length_keeps_description_separator() -> None:
    assert CompletionPopup.rendered_text_length("@abc", "def") == 8 + GLYPH_WIDTH


def test_rendered_text_length_omits_glyph_for_plain_label() -> None:
    # Labels without a leading sigil (e.g. plain text) don't render a glyph.
    assert CompletionPopup.rendered_text_length("abc", "") == 3
