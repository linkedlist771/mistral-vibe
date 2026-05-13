"""Tests for the Claude-Code-parity tools added to vibe.

Covers: glob, sleep, notebook_edit, tool_search, task_tracker (TaskCreate/...),
worktree, cron, push_notification.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
import tempfile

import pytest

from vibe.core import tasks_store
from vibe.core.tools.base import ToolError


async def _drain(invoke_gen):
    last = None
    async for ev in invoke_gen:
        last = ev
    return last


@pytest.mark.asyncio
async def test_glob_finds_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("a")
    (tmp_path / "b.py").write_text("b")
    (tmp_path / "c.txt").write_text("c")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "d.py").write_text("d")

    from vibe.core.tools.builtins.glob import Glob, GlobConfig

    tool = Glob.from_config(lambda: GlobConfig())
    result = await _drain(tool.invoke(pattern="**/*.py", path=str(tmp_path)))
    assert result is not None
    assert result.total_found == 3
    paths = {Path(m.path).name for m in result.matches}
    assert paths == {"a.py", "b.py", "d.py"}


@pytest.mark.asyncio
async def test_glob_rejects_invalid_path(tmp_path: Path) -> None:
    from vibe.core.tools.builtins.glob import Glob, GlobConfig

    tool = Glob.from_config(lambda: GlobConfig())
    with pytest.raises(ToolError):
        await _drain(tool.invoke(pattern="*", path=str(tmp_path / "missing")))


@pytest.mark.asyncio
async def test_sleep_short(tmp_path: Path) -> None:
    from vibe.core.tools.builtins.sleep import Sleep, SleepConfig

    tool = Sleep.from_config(lambda: SleepConfig())
    result = await _drain(tool.invoke(milliseconds=15, reason="brief"))
    assert result.slept_ms == 15
    assert result.reason == "brief"


@pytest.mark.asyncio
async def test_sleep_validates_bounds() -> None:
    from vibe.core.tools.builtins.sleep import Sleep, SleepConfig

    tool = Sleep.from_config(lambda: SleepConfig())
    with pytest.raises(ToolError):
        await _drain(tool.invoke(milliseconds=999999))


@pytest.mark.asyncio
async def test_notebook_edit_insert_and_replace(tmp_path: Path) -> None:
    from vibe.core.tools.builtins.notebook_edit import (
        NotebookEdit,
        NotebookEditConfig,
    )

    p = tmp_path / "n.ipynb"
    p.write_text(json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}))

    tool = NotebookEdit.from_config(lambda: NotebookEditConfig())
    res = await _drain(
        tool.invoke(
            notebook_path=str(p), new_source="print(1)", cell_type="code", edit_mode="insert"
        )
    )
    assert res.edit_mode == "insert"
    assert res.cell_count == 1
    cell_id = res.cell_id

    res = await _drain(
        tool.invoke(
            notebook_path=str(p), new_source="print(2)", cell_id=cell_id, edit_mode="replace"
        )
    )
    assert res.edit_mode == "replace"

    data = json.loads(p.read_text())
    src = data["cells"][0]["source"]
    assert "".join(src) == "print(2)"


@pytest.mark.asyncio
async def test_notebook_edit_delete(tmp_path: Path) -> None:
    from vibe.core.tools.builtins.notebook_edit import (
        NotebookEdit,
        NotebookEditConfig,
    )

    p = tmp_path / "n.ipynb"
    p.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "id": "a",
                        "metadata": {},
                        "source": ["x=1"],
                        "execution_count": None,
                        "outputs": [],
                    }
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        )
    )
    tool = NotebookEdit.from_config(lambda: NotebookEditConfig())
    res = await _drain(tool.invoke(notebook_path=str(p), cell_id="a", edit_mode="delete"))
    assert res.cell_count == 0


@pytest.mark.asyncio
async def test_notebook_edit_rejects_missing() -> None:
    from vibe.core.tools.builtins.notebook_edit import (
        NotebookEdit,
        NotebookEditConfig,
    )

    tool = NotebookEdit.from_config(lambda: NotebookEditConfig())
    with pytest.raises(ToolError):
        await _drain(tool.invoke(notebook_path="/no/such.ipynb", edit_mode="delete", cell_id="x"))


@pytest.mark.asyncio
async def test_tool_search_returns_matches() -> None:
    from vibe.core.tools.builtins.tool_search import ToolSearch, ToolSearchConfig

    tool = ToolSearch.from_config(lambda: ToolSearchConfig())
    result = await _drain(tool.invoke(query="read file content"))
    names = {m.name for m in result.matches}
    assert "read_file" in names


@pytest.mark.asyncio
async def test_tool_search_select_form() -> None:
    from vibe.core.tools.builtins.tool_search import ToolSearch, ToolSearchConfig

    tool = ToolSearch.from_config(lambda: ToolSearchConfig())
    result = await _drain(tool.invoke(query="select:glob,read_file"))
    names = {m.name for m in result.matches}
    assert names == {"glob", "read_file"}


@pytest.mark.asyncio
async def test_task_create_get_list_update(tmp_path: Path) -> None:
    tasks_store.reset_default_store()
    tasks_store.get_default_store(tmp_path / "tasks.json")

    from vibe.core.tools.builtins.task_tracker import (
        TaskCreate,
        TaskCreateConfig,
        TaskGet,
        TaskGetConfig,
        TaskList,
        TaskListConfig,
        TaskUpdate,
        TaskUpdateConfig,
    )

    creator = TaskCreate.from_config(lambda: TaskCreateConfig())
    created = await _drain(creator.invoke(subject="ship feature", description="impl"))
    assert created.id

    getter = TaskGet.from_config(lambda: TaskGetConfig())
    fetched = await _drain(getter.invoke(task_id=created.id))
    assert fetched.found
    assert fetched.task.subject == "ship feature"

    lister = TaskList.from_config(lambda: TaskListConfig())
    listed = await _drain(lister.invoke())
    assert listed.total == 1

    updater = TaskUpdate.from_config(lambda: TaskUpdateConfig())
    updated = await _drain(updater.invoke(task_id=created.id, status="in_progress"))
    assert updated.status.value == "in_progress"

    tasks_store.reset_default_store()


@pytest.mark.asyncio
async def test_task_output_and_stop(tmp_path: Path) -> None:
    tasks_store.reset_default_store()
    tasks_store.get_default_store(tmp_path / "tasks.json")

    from vibe.core.tools.builtins.task_tracker import (
        TaskCreate,
        TaskCreateConfig,
        TaskOutput,
        TaskOutputConfig,
        TaskStop,
        TaskStopConfig,
    )

    creator = TaskCreate.from_config(lambda: TaskCreateConfig())
    created = await _drain(creator.invoke(subject="task1"))

    outputter = TaskOutput.from_config(lambda: TaskOutputConfig())
    w = await _drain(outputter.invoke(task_id=created.id, output="result text"))
    assert w.written
    r = await _drain(outputter.invoke(task_id=created.id))
    assert r.output == "result text"

    stopper = TaskStop.from_config(lambda: TaskStopConfig())
    s = await _drain(stopper.invoke(task_id=created.id, reason="done"))
    assert s.new_status.value == "completed"

    tasks_store.reset_default_store()


@pytest.mark.asyncio
async def test_task_get_missing_returns_not_found(tmp_path: Path) -> None:
    tasks_store.reset_default_store()
    tasks_store.get_default_store(tmp_path / "tasks.json")

    from vibe.core.tools.builtins.task_tracker import TaskGet, TaskGetConfig

    tool = TaskGet.from_config(lambda: TaskGetConfig())
    r = await _drain(tool.invoke(task_id="missing"))
    assert not r.found

    tasks_store.reset_default_store()


@pytest.mark.asyncio
async def test_push_notification_fires() -> None:
    from vibe.core.tools.builtins.push_notification import (
        PushNotification,
        PushNotificationConfig,
    )

    tool = PushNotification.from_config(lambda: PushNotificationConfig())
    r = await _drain(tool.invoke(title="Done", message="Tests pass", bell=False))
    assert r.delivered


@pytest.mark.asyncio
async def test_cron_create_list_delete(tmp_path: Path, monkeypatch) -> None:
    from vibe.core.tools.builtins import cron as cron_mod

    monkeypatch.setattr(cron_mod, "_cron_file", lambda: tmp_path / "cron.json")

    from vibe.core.tools.builtins.cron import (
        CronCreate,
        CronCreateConfig,
        CronDelete,
        CronDeleteConfig,
        CronList,
        CronListConfig,
    )

    c = CronCreate.from_config(lambda: CronCreateConfig())
    created = await _drain(c.invoke(schedule="5m", prompt="ping"))
    assert created.job_id

    lister = CronList.from_config(lambda: CronListConfig())
    listed = await _drain(lister.invoke())
    assert listed.total == 1

    deleter = CronDelete.from_config(lambda: CronDeleteConfig())
    d = await _drain(deleter.invoke(job_id=created.job_id))
    assert d.removed

    listed = await _drain(lister.invoke())
    assert listed.total == 0


@pytest.mark.asyncio
async def test_worktree_create_and_remove(tmp_path: Path) -> None:
    # init a real git repo so EnterWorktree/ExitWorktree work
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "f.txt").write_text("hi")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "init"], check=True
    )

    import os

    old_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        from vibe.core.tools.builtins.worktree import (
            EnterWorktree,
            EnterWorktreeConfig,
            ExitWorktree,
            ExitWorktreeConfig,
        )

        wt_path = tmp_path / "wt"
        enter = EnterWorktree.from_config(lambda: EnterWorktreeConfig())
        created = await _drain(
            enter.invoke(name="exp", path=str(wt_path))
        )
        assert Path(created.path).is_dir()
        assert created.branch == "vibe/exp"

        exitter = ExitWorktree.from_config(lambda: ExitWorktreeConfig())
        removed = await _drain(
            exitter.invoke(path=str(wt_path), action="remove", discard_changes=True)
        )
        assert "remove" in removed.message.lower()
    finally:
        os.chdir(old_cwd)
