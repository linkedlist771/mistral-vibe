"""Tests for the persistent memory subsystem."""
from __future__ import annotations

from pathlib import Path

import pytest

from vibe.core.memory import MemoryEntry, get_memory_store
from vibe.core.memory import _store as memory_store_module


@pytest.fixture(autouse=True)
def _reset_store():
    memory_store_module.reset_memory_store()
    yield
    memory_store_module.reset_memory_store()


def test_save_and_list_memory(tmp_path: Path) -> None:
    store = get_memory_store(tmp_path)
    assert store.list_memories() == []

    entry = MemoryEntry(
        name="user-preferences",
        description="user prefers terse output",
        metadata_type="feedback",
        body="user said: stop writing summaries at end of responses",
        path=tmp_path / "user-preferences.md",
        raw_metadata={"type": "feedback"},
    )
    store.save(entry)

    listed = store.list_memories()
    assert len(listed) == 1
    name, fetched = listed[0]
    assert name == "user-preferences"
    assert fetched.metadata_type == "feedback"
    assert "stop writing summaries" in fetched.body


def test_index_updated_on_save(tmp_path: Path) -> None:
    store = get_memory_store(tmp_path)
    store.save(
        MemoryEntry(
            name="a",
            description="first",
            metadata_type="user",
            body="body",
            path=tmp_path / "a.md",
        )
    )
    store.save(
        MemoryEntry(
            name="b",
            description="second",
            metadata_type="project",
            body="body",
            path=tmp_path / "b.md",
        )
    )
    idx = store.index_path.read_text()
    assert "[a]" in idx
    assert "[b]" in idx


def test_remove_memory(tmp_path: Path) -> None:
    store = get_memory_store(tmp_path)
    store.save(
        MemoryEntry(
            name="x",
            description="ephemeral",
            metadata_type="user",
            body="body",
            path=tmp_path / "x.md",
        )
    )
    assert len(store.list_memories()) == 1
    assert store.remove("x")
    assert store.list_memories() == []


def test_prompt_section_builds(tmp_path: Path) -> None:
    store = get_memory_store(tmp_path)
    store.save(
        MemoryEntry(
            name="thing",
            description="desc here",
            metadata_type="reference",
            body="details about a thing",
            path=tmp_path / "thing.md",
        )
    )
    section = store.build_prompt_section()
    assert section.startswith("# Memory")
    assert "thing" in section
    assert "details about a thing" in section


def test_invalid_frontmatter_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "broken.md").write_text("not a memory file")
    store = get_memory_store(tmp_path)
    assert store.list_memories() == []


def test_index_skipped_in_list(tmp_path: Path) -> None:
    store = get_memory_store(tmp_path)
    # MEMORY.md is created on first save; ensure it's not enumerated
    store.save(
        MemoryEntry(
            name="a",
            description="d",
            metadata_type="user",
            body="b",
            path=tmp_path / "a.md",
        )
    )
    names = [n for n, _ in store.list_memories()]
    assert names == ["a"]
