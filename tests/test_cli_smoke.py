"""Smoke tests: run the CLI as a subprocess against a real API endpoint.

These tests require:
- the ANTHROPIC_API_KEY env var set
- the spark-llm router reachable at the configured api_base

If either is missing, the tests skip.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _have_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_COMPATIBALE_API_KEY"))


@pytest.mark.skipif(not _have_api_key(), reason="no API key for end-to-end test")
@pytest.mark.timeout(120)
def test_cli_prints_hi(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.setdefault(
        "ANTHROPIC_API_KEY",
        os.environ.get("ANTHROPIC_COMPATIBALE_API_KEY", "local-router-key"),
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vibe.cli.entrypoint",
            "-p",
            "say hi in exactly one word",
            "--trust",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=90,
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    # The response should contain some text
    assert result.stdout.strip(), "expected non-empty stdout"


def test_cli_version_flag_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vibe.cli.entrypoint", "--version"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout.strip()


def test_cli_help_flag_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vibe.cli.entrypoint", "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Claude Code" in result.stdout or "interactive CLI" in result.stdout


def test_tool_discovery_finds_new_tools() -> None:
    """Static smoke test: the new tools are findable by ToolManager."""
    from vibe.core.paths import DEFAULT_TOOL_DIR
    from vibe.core.tools.manager import ToolManager

    discovered = {
        cls.get_name()
        for cls in ToolManager._iter_tool_classes([DEFAULT_TOOL_DIR.path])
    }
    must_have = {
        "glob",
        "sleep",
        "notebook_edit",
        "tool_search",
        "task_create",
        "task_get",
        "task_list",
        "task_update",
        "task_output",
        "task_stop",
        "enter_worktree",
        "exit_worktree",
        "cron_create",
        "cron_list",
        "cron_delete",
        "push_notification",
    }
    missing = must_have - discovered
    assert not missing, f"missing tools: {missing}"
