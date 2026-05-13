"""Direct tests for the JSON-backed task store."""
from __future__ import annotations

from pathlib import Path

import pytest

from vibe.core.tasks_store import TaskStatus, TaskStore


@pytest.fixture()
def store(tmp_path: Path) -> TaskStore:
    return TaskStore(tmp_path / "tasks.json")


def test_create_returns_task_with_id(store: TaskStore) -> None:
    task = store.create(subject="do thing")
    assert task.id
    assert task.subject == "do thing"
    assert task.status == TaskStatus.PENDING


def test_create_persists_to_disk(tmp_path: Path) -> None:
    p = tmp_path / "t.json"
    s1 = TaskStore(p)
    created = s1.create(subject="thing")
    # New store reads same file
    s2 = TaskStore(p)
    assert s2.get(created.id) is not None


def test_list_excludes_deleted_by_default(store: TaskStore) -> None:
    a = store.create(subject="keep")
    b = store.create(subject="drop")
    store.delete(b.id)
    listed = store.list()
    ids = {t.id for t in listed}
    assert a.id in ids
    assert b.id not in ids


def test_list_includes_deleted_when_requested(store: TaskStore) -> None:
    a = store.create(subject="keep")
    b = store.create(subject="drop")
    store.delete(b.id)
    listed = store.list(include_deleted=True)
    ids = {t.id for t in listed}
    assert {a.id, b.id} <= ids


def test_update_changes_status(store: TaskStore) -> None:
    t = store.create(subject="x")
    store.update(t.id, status=TaskStatus.IN_PROGRESS)
    fetched = store.get(t.id)
    assert fetched.status == TaskStatus.IN_PROGRESS


def test_update_metadata_supports_delete(store: TaskStore) -> None:
    t = store.create(subject="m", metadata={"k": "v"})
    store.update(t.id, metadata={"k": None, "k2": "v2"})
    f = store.get(t.id)
    assert "k" not in f.metadata
    assert f.metadata["k2"] == "v2"


def test_update_unknown_raises(store: TaskStore) -> None:
    with pytest.raises(KeyError):
        store.update("nope", status=TaskStatus.COMPLETED)


def test_set_output(store: TaskStore) -> None:
    t = store.create(subject="o")
    store.set_output(t.id, "long output here")
    assert store.get(t.id).output == "long output here"


def test_dependencies_dedup(store: TaskStore) -> None:
    a = store.create(subject="a")
    b = store.create(subject="b")
    store.update(b.id, add_blocked_by=[a.id, a.id])
    assert store.get(b.id).blocked_by == [a.id]
