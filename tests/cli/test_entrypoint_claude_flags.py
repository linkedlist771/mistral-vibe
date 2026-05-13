"""Tests for the Claude Code-compatible CLI flag aliases.

Covers ``--dangerously-skip-permissions``, ``--permission-mode``, ``--print``,
``--allowed-tools`` / ``--disallowed-tools``, ``--model``, ``--add-dir``,
``--system-prompt`` / ``--append-system-prompt`` and the ``--output-format``
``stream-json`` alias.
"""
from __future__ import annotations

import argparse
import os

import pytest

from vibe.cli.entrypoint import (
    _PERMISSION_MODE_TO_AGENT,
    _resolve_claude_code_flag_aliases,
    parse_arguments,
)


def _parse(*argv: str) -> argparse.Namespace:
    """Run ``parse_arguments`` with a controlled argv."""
    import sys

    original = sys.argv
    try:
        sys.argv = ["vibe", *argv]
        return parse_arguments()
    finally:
        sys.argv = original


_AFFECTED_ENV_VARS = (
    "VIBE_ACTIVE_MODEL",
    "VIBE_SYSTEM_PROMPT",
    "VIBE_APPEND_SYSTEM_PROMPT",
    "VIBE_DISABLED_TOOLS",
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Wipe the env vars the resolver writes BEFORE the test and ensure
    monkeypatch restores them after, so cross-test pollution can't happen.

    ``_resolve_claude_code_flag_aliases`` uses ``os.environ.setdefault`` for
    writes, which would otherwise leak between tests.
    """
    saved = {k: os.environ.get(k) for k in _AFFECTED_ENV_VARS}
    for k in _AFFECTED_ENV_VARS:
        monkeypatch.delenv(k, raising=False)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _clear_env(monkeypatch) -> None:
    """Compatibility shim — autouse fixture already isolates env."""
    for k in _AFFECTED_ENV_VARS:
        monkeypatch.delenv(k, raising=False)


def test_dangerously_skip_permissions_implies_auto_approve_agent(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse("--dangerously-skip-permissions", "-p", "hello")
    assert args.dangerously_skip_permissions is True
    _resolve_claude_code_flag_aliases(args)
    assert args.agent == "auto-approve"


def test_print_is_alias_for_prompt(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse("--print", "hi there")
    assert args.prompt == "hi there"


def test_permission_mode_maps_to_agent(monkeypatch) -> None:
    _clear_env(monkeypatch)
    for mode, expected in _PERMISSION_MODE_TO_AGENT.items():
        args = _parse("--permission-mode", mode, "-p", "x")
        _resolve_claude_code_flag_aliases(args)
        assert args.agent == expected, f"{mode} should map to {expected}"


def test_explicit_agent_beats_permission_mode(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse(
        "--permission-mode",
        "bypassPermissions",
        "--agent",
        "plan",
        "-p",
        "x",
    )
    _resolve_claude_code_flag_aliases(args)
    assert args.agent == "plan"


def test_dangerously_skip_overrides_explicit_agent(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse(
        "--dangerously-skip-permissions",
        "--agent",
        "plan",
        "-p",
        "x",
    )
    _resolve_claude_code_flag_aliases(args)
    assert args.agent == "auto-approve"


def test_allowed_tools_alias_populates_enabled_tools(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse(
        "--allowed-tools", "bash", "--allowed-tools", "read_file", "-p", "x"
    )
    assert args.enabled_tools == ["bash", "read_file"]


def test_allowed_tools_camelcase_alias(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse("--allowedTools", "bash", "-p", "x")
    assert args.enabled_tools == ["bash"]


def test_disallowed_tools_sets_env_var_as_json(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse(
        "--disallowed-tools", "bash", "--disallowed-tools", "write_file", "-p", "x"
    )
    _resolve_claude_code_flag_aliases(args)
    raw = os.environ.get("VIBE_DISABLED_TOOLS")
    assert raw is not None
    import json

    assert json.loads(raw) == ["bash", "write_file"]


def test_model_flag_sets_env_var(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse("--model", "gpt-5.5(high)", "-p", "x")
    _resolve_claude_code_flag_aliases(args)
    assert os.environ["VIBE_ACTIVE_MODEL"] == "gpt-5.5(high)"


def test_add_dir_collects_multiple(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse("--add-dir", "/tmp/a", "--add-dir", "/tmp/b", "-p", "x")
    assert args.add_dir == ["/tmp/a", "/tmp/b"]


def test_add_dir_defaults_empty(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse("-p", "x")
    assert args.add_dir == []


def test_system_prompt_sets_env_var(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse("--system-prompt", "Be terse.", "-p", "x")
    _resolve_claude_code_flag_aliases(args)
    assert os.environ["VIBE_SYSTEM_PROMPT"] == "Be terse."


def test_append_system_prompt_sets_env_var(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse("--append-system-prompt", "PS: ship it.", "-p", "x")
    _resolve_claude_code_flag_aliases(args)
    assert os.environ["VIBE_APPEND_SYSTEM_PROMPT"] == "PS: ship it."


def test_output_format_alias_and_stream_json(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse("--output-format", "stream-json", "-p", "x")
    _resolve_claude_code_flag_aliases(args)
    # `stream-json` is normalized to vibe's `streaming` value.
    assert args.output == "streaming"


def test_output_format_text_default(monkeypatch) -> None:
    _clear_env(monkeypatch)
    args = _parse("-p", "x")
    assert args.output == "text"


def test_no_dangerously_skip_no_implicit_trust(monkeypatch) -> None:
    """``--dangerously-skip-permissions`` is the only flag that should imply
    trust. Plain ``-p`` runs do not auto-trust the cwd."""
    _clear_env(monkeypatch)
    args = _parse("-p", "x")
    assert args.dangerously_skip_permissions is False
    assert args.trust is False
