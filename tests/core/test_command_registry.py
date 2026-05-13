"""Tests for the CommandRegistry, especially the new Claude-Code-style commands."""
from __future__ import annotations

import pytest

from vibe.cli.commands import CommandRegistry


def test_new_commands_registered() -> None:
    reg = CommandRegistry()
    for name in [
        "init",
        "review",
        "security-review",
        "commit",
        "pr",
        "agents",
        "skills",
        "memory",
        "doctor",
        "tasks",
        "version",
    ]:
        assert reg.has_command(name), f"missing /{name}"


def test_command_aliases_are_unique() -> None:
    reg = CommandRegistry()
    seen: set[str] = set()
    for cmd in reg.commands.values():
        for alias in cmd.aliases:
            assert alias not in seen, f"duplicate alias: {alias}"
            seen.add(alias)


def test_help_text_includes_new_commands() -> None:
    reg = CommandRegistry()
    help_text = reg.get_help_text()
    for needle in ["/init", "/review", "/security-review", "/memory", "/agents"]:
        assert needle in help_text, f"{needle} missing from help"


def test_parse_command_dispatches() -> None:
    reg = CommandRegistry()
    parsed = reg.parse_command("/init")
    assert parsed is not None
    name, command, args = parsed
    assert name == "init"
    assert command.handler == "_run_init_skill"
    assert args == ""

    parsed = reg.parse_command("/review with focus on tests")
    assert parsed is not None
    name, _, args = parsed
    assert name == "review"
    assert args == "with focus on tests"


def test_parse_command_returns_none_for_unknown() -> None:
    reg = CommandRegistry()
    assert reg.parse_command("/totally-not-real") is None


def test_excluded_commands_are_hidden() -> None:
    reg = CommandRegistry(excluded_commands=["init", "review"])
    assert not reg.has_command("init")
    assert not reg.has_command("review")
    assert reg.has_command("commit")
