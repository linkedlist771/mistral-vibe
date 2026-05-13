"""Persistent task store backing the TaskCreate/Get/List/Update/Output/Stop tools.

This is a project-scoped task list (~/.vibe/tasks.json or ./.vibe/tasks.json).
Unlike the simple in-memory Todo tool, tasks here persist across sessions and
support dependencies, owners, and longer-form text content (task output).
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import json
from pathlib import Path
import threading
from typing import Any, ClassVar
import uuid

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELETED = "deleted"


class StoredTask(BaseModel):
    id: str
    subject: str
    description: str = ""
    active_form: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    owner: str | None = None
    blocked_by: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)
    output: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class TaskStore:
    """Thread-safe JSON-backed task list."""

    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, path: Path) -> None:
        self.path = path
        self._tasks: dict[str, StoredTask] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for raw in data.get("tasks", []):
            try:
                t = StoredTask.model_validate(raw)
                self._tasks[t.id] = t
            except Exception:
                continue

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "tasks": [t.model_dump(mode="json") for t in self._tasks.values()],
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def create(
        self,
        *,
        subject: str,
        description: str = "",
        active_form: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredTask:
        with self._lock:
            now = datetime.now(UTC).isoformat()
            task = StoredTask(
                id=str(uuid.uuid4())[:8],
                subject=subject,
                description=description,
                active_form=active_form,
                metadata=metadata or {},
                created_at=now,
                updated_at=now,
            )
            self._tasks[task.id] = task
            self._save()
            return task

    def get(self, task_id: str) -> StoredTask | None:
        return self._tasks.get(task_id)

    def list(self, *, include_deleted: bool = False) -> list[StoredTask]:
        items = list(self._tasks.values())
        if not include_deleted:
            items = [t for t in items if t.status != TaskStatus.DELETED]
        items.sort(key=lambda t: t.created_at)
        return items

    def update(
        self,
        task_id: str,
        *,
        subject: str | None = None,
        description: str | None = None,
        active_form: str | None = None,
        status: TaskStatus | None = None,
        owner: str | None = None,
        add_blocked_by: list[str] | None = None,
        add_blocks: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredTask:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)
            if subject is not None:
                task.subject = subject
            if description is not None:
                task.description = description
            if active_form is not None:
                task.active_form = active_form
            if status is not None:
                task.status = status
            if owner is not None:
                task.owner = owner
            if add_blocked_by:
                task.blocked_by = list({*task.blocked_by, *add_blocked_by})
            if add_blocks:
                task.blocks = list({*task.blocks, *add_blocks})
            if metadata:
                for k, v in metadata.items():
                    if v is None:
                        task.metadata.pop(k, None)
                    else:
                        task.metadata[k] = v
            task.updated_at = datetime.now(UTC).isoformat()
            self._save()
            return task

    def set_output(self, task_id: str, output: str) -> StoredTask:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)
            task.output = output
            task.updated_at = datetime.now(UTC).isoformat()
            self._save()
            return task

    def delete(self, task_id: str) -> StoredTask:
        return self.update(task_id, status=TaskStatus.DELETED)


_DEFAULT_STORE: TaskStore | None = None


def get_default_store(root: Path | None = None) -> TaskStore:
    global _DEFAULT_STORE
    if root is None:
        root = Path.cwd() / ".vibe" / "tasks.json"
    if _DEFAULT_STORE is None or _DEFAULT_STORE.path != root:
        _DEFAULT_STORE = TaskStore(root)
    return _DEFAULT_STORE


def reset_default_store() -> None:
    global _DEFAULT_STORE
    _DEFAULT_STORE = None
