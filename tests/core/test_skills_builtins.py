"""Tests for the bundled (builtin) skills."""
from __future__ import annotations

from vibe.core.skills.builtins import BUILTIN_SKILLS


def test_builtin_skills_loaded() -> None:
    expected = {"vibe", "init", "review", "security-review", "commit", "pr"}
    assert expected.issubset(set(BUILTIN_SKILLS.keys()))


def test_skills_have_required_fields() -> None:
    for name, skill in BUILTIN_SKILLS.items():
        assert skill.name == name
        assert skill.description
        assert skill.prompt
        # All user-facing slash skills must be invocable
        if name != "vibe":
            assert skill.user_invocable, f"{name} should be user_invocable"


def test_review_skill_mentions_review_steps() -> None:
    review = BUILTIN_SKILLS["review"]
    body = review.prompt.lower()
    assert "git" in body
    assert "correctness" in body or "review" in body


def test_security_review_skill_covers_injection() -> None:
    sec = BUILTIN_SKILLS["security-review"]
    body = sec.prompt.lower()
    assert "injection" in body
    assert "xss" in body or "cross-site" in body


def test_init_skill_writes_agents_md() -> None:
    init = BUILTIN_SKILLS["init"]
    body = init.prompt.lower()
    assert "agents.md" in body
