from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError
import yaml

from vibe.core.paths import VIBE_HOME


MEMORY_TYPES = {"user", "feedback", "project", "reference"}
MAX_INDEX_LINES = 200
MAX_INDEX_LINE_LEN = 200


class MemoryFrontmatter(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=400)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def metadata_type(self) -> str:
        t = str(self.metadata.get("type", "user")).lower()
        return t if t in MEMORY_TYPES else "user"


@dataclass
class MemoryEntry:
    """A single memory: frontmatter metadata + body text."""

    name: str
    description: str
    metadata_type: str
    body: str
    path: Path
    raw_metadata: dict[str, Any] = field(default_factory=dict)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def _parse_memory(text: str, path: Path) -> MemoryEntry | None:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    fm_raw = match.group(1)
    body = match.group(2).strip()
    try:
        data = yaml.safe_load(fm_raw) or {}
        if not isinstance(data, dict):
            return None
        fm = MemoryFrontmatter.model_validate(data)
    except (yaml.YAMLError, ValidationError):
        return None
    return MemoryEntry(
        name=fm.name,
        description=fm.description,
        metadata_type=fm.metadata_type,
        body=body,
        path=path,
        raw_metadata=fm.metadata,
    )


def _format_memory(entry: MemoryEntry) -> str:
    fm = {
        "name": entry.name,
        "description": entry.description,
        "metadata": entry.raw_metadata or {"type": entry.metadata_type},
    }
    fm_yaml = yaml.safe_dump(fm, sort_keys=False).strip()
    return f"---\n{fm_yaml}\n---\n\n{entry.body.strip()}\n"


class MemoryStore:
    """File-based memory store.

    Directory layout:
        memory_dir/
            MEMORY.md           # index, one bullet per memory
            <slug>.md           # individual memory files
    """

    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.memory_dir / "MEMORY.md"

    def list_memories(self) -> list[tuple[str, MemoryEntry]]:
        entries: list[tuple[str, MemoryEntry]] = []
        for path in sorted(self.memory_dir.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            entry = _parse_memory(text, path)
            if entry is None:
                continue
            entries.append((entry.name, entry))
        return entries

    def get(self, name: str) -> MemoryEntry | None:
        for n, entry in self.list_memories():
            if n == name:
                return entry
        return None

    def save(self, entry: MemoryEntry) -> Path:
        slug = re.sub(r"[^a-z0-9_-]+", "-", entry.name.lower()).strip("-") or "memory"
        target = self.memory_dir / f"{slug}.md"
        target.write_text(_format_memory(entry), encoding="utf-8")
        self._update_index()
        return target

    def remove(self, name: str) -> bool:
        entry = self.get(name)
        if entry is None:
            return False
        try:
            entry.path.unlink()
        except OSError:
            return False
        self._update_index()
        return True

    def _update_index(self) -> None:
        entries = self.list_memories()
        lines: list[str] = []
        for _, entry in entries:
            rel = entry.path.name
            line = f"- [{entry.name}]({rel}) — {entry.description}"
            if len(line) > MAX_INDEX_LINE_LEN:
                line = line[: MAX_INDEX_LINE_LEN - 1] + "…"
            lines.append(line)
        lines = lines[:MAX_INDEX_LINES]
        if not lines:
            lines = ["_(No memories yet.)_"]
        ts = datetime.now(UTC).strftime("%Y-%m-%d")
        header = f"# Memory index — updated {ts}\n\n"
        self.index_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")

    def build_prompt_section(self, *, limit_chars: int = 8000) -> str:
        """Return a markdown block suitable for injection into the system prompt."""
        entries = self.list_memories()
        if not entries:
            return ""
        chunks: list[str] = ["# Memory", ""]
        size = 0
        for _, entry in entries:
            chunk = (
                f"## {entry.name} ({entry.metadata_type})\n"
                f"{entry.description}\n\n"
                f"{entry.body.strip()}\n"
            )
            if size + len(chunk) > limit_chars:
                chunks.append(f"_...{len(entries) - chunks.count('## ')} more memories truncated for prompt budget._")
                break
            chunks.append(chunk)
            size += len(chunk)
        return "\n".join(chunks).strip()


_DEFAULT_STORE: MemoryStore | None = None


def get_memory_store(memory_dir: Path | None = None) -> MemoryStore:
    global _DEFAULT_STORE
    if memory_dir is None:
        memory_dir = Path(VIBE_HOME.path) / "memory"
    if _DEFAULT_STORE is None or _DEFAULT_STORE.memory_dir != memory_dir:
        _DEFAULT_STORE = MemoryStore(memory_dir)
    return _DEFAULT_STORE


def reset_memory_store() -> None:
    global _DEFAULT_STORE
    _DEFAULT_STORE = None
