"""Tests for the expanded sub-agent catalog."""
from __future__ import annotations

from vibe.core.agents.models import (
    BUILTIN_AGENTS,
    AgentType,
    BuiltinAgentName,
)


def test_general_purpose_agent_exists() -> None:
    a = BUILTIN_AGENTS[BuiltinAgentName.GENERAL_PURPOSE]
    assert a.agent_type == AgentType.SUBAGENT
    enabled = a.overrides.get("enabled_tools", [])
    assert "bash" in enabled
    assert "glob" in enabled


def test_code_reviewer_is_subagent_and_read_only_bash() -> None:
    a = BUILTIN_AGENTS[BuiltinAgentName.CODE_REVIEWER]
    assert a.agent_type == AgentType.SUBAGENT
    bash_cfg = a.overrides.get("tools", {}).get("bash", {})
    allowlist = bash_cfg.get("allowlist", [])
    # only git read commands
    assert all(cmd.startswith("git") for cmd in allowlist)


def test_plan_subagent_only_reads() -> None:
    a = BUILTIN_AGENTS[BuiltinAgentName.PLAN_SUBAGENT]
    assert a.agent_type == AgentType.SUBAGENT
    enabled = a.overrides.get("enabled_tools", [])
    # should not include destructive tools
    assert "write_file" not in enabled
    assert "search_replace" not in enabled


def test_task_tool_allowlist_includes_new_subagents() -> None:
    from vibe.core.tools.builtins.task import TaskToolConfig

    cfg = TaskToolConfig()
    assert BuiltinAgentName.EXPLORE in cfg.allowlist
    assert BuiltinAgentName.GENERAL_PURPOSE in cfg.allowlist
    assert BuiltinAgentName.CODE_REVIEWER in cfg.allowlist
