"""Persistent file-based memory system, modeled on Claude Code's memdir.

Each memory is a markdown file with YAML frontmatter plus a body. The
`MEMORY.md` file in the memory directory acts as a one-line index pointing to
every memory file. The memory directory is loaded into the system prompt at
agent boot so prior conversations can inform future ones.
"""
from __future__ import annotations

from vibe.core.memory._store import MemoryEntry, MemoryStore, get_memory_store

__all__ = ["MemoryEntry", "MemoryStore", "get_memory_store"]
