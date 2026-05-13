"""Persistent task-tracking tools: task_create, task_get, task_list, task_update, task_output, task_stop.

Modeled on Claude Code's TaskCreate/TaskGet/TaskList/TaskUpdate/TaskOutput/TaskStop tools.
These are distinct from the simple in-memory `todo` tool — these tasks persist on disk and
support dependencies, status transitions, and stored output text.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from vibe.core.tasks_store import StoredTask, TaskStatus, get_default_store
from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    InvokeContext,
    ToolError,
    ToolPermission,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData
from vibe.core.types import ToolResultEvent, ToolStreamEvent


def _store_path(ctx: InvokeContext | None) -> Path | None:
    return None


class TaskCreateArgs(BaseModel):
    subject: str = Field(description="Brief, actionable title (imperative form).")
    description: str = Field(
        default="", description="Longer description of what the task is and why."
    )
    active_form: str | None = Field(
        default=None,
        description=(
            "Present-continuous label shown in progress UI (e.g. 'Running tests')."
        ),
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Arbitrary key/value metadata."
    )


class TaskCreateResult(BaseModel):
    id: str
    subject: str
    status: TaskStatus
    message: str = ""


class TaskCreateConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class TaskCreateState(BaseToolState):
    pass


class TaskCreate(
    BaseTool[TaskCreateArgs, TaskCreateResult, TaskCreateConfig, TaskCreateState],
    ToolUIData[TaskCreateArgs, TaskCreateResult],
):
    description: ClassVar[str] = (
        "Create a structured task in the persistent task list. Use this when "
        "you have a multi-step task to track. Tasks survive across sessions."
    )

    @classmethod
    def format_call_display(cls, args: TaskCreateArgs) -> ToolCallDisplay:
        return ToolCallDisplay(summary=f"TaskCreate '{args.subject}'")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, TaskCreateResult):
            return ToolResultDisplay(success=True, message=f"Task {event.result.id} created")
        return ToolResultDisplay(success=True, message="Created")

    @classmethod
    def get_status_text(cls) -> str:
        return "Creating task"

    async def run(
        self, args: TaskCreateArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | TaskCreateResult, None]:
        store = get_default_store()
        task = store.create(
            subject=args.subject,
            description=args.description,
            active_form=args.active_form,
            metadata=args.metadata,
        )
        yield TaskCreateResult(
            id=task.id,
            subject=task.subject,
            status=task.status,
            message=f"Task #{task.id} created: {task.subject}",
        )


class TaskGetArgs(BaseModel):
    task_id: str = Field(description="ID of the task to fetch.")


class TaskGetResult(BaseModel):
    task: StoredTask | None
    found: bool


class TaskGetConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class TaskGet(
    BaseTool[TaskGetArgs, TaskGetResult, TaskGetConfig, BaseToolState],
    ToolUIData[TaskGetArgs, TaskGetResult],
):
    description: ClassVar[str] = (
        "Fetch a task by id, including its subject, status, description, output, "
        "blockers, owner, and metadata."
    )

    @classmethod
    def format_call_display(cls, args: TaskGetArgs) -> ToolCallDisplay:
        return ToolCallDisplay(summary=f"TaskGet {args.task_id}")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, TaskGetResult) and event.result.task:
            return ToolResultDisplay(
                success=True,
                message=f"Task {event.result.task.id}: {event.result.task.subject}",
            )
        return ToolResultDisplay(success=False, message="Not found")

    @classmethod
    def get_status_text(cls) -> str:
        return "Fetching task"

    async def run(
        self, args: TaskGetArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | TaskGetResult, None]:
        store = get_default_store()
        task = store.get(args.task_id)
        yield TaskGetResult(task=task, found=task is not None)


class TaskListArgs(BaseModel):
    include_deleted: bool = Field(
        default=False, description="Whether to include deleted tasks."
    )


class TaskSummary(BaseModel):
    id: str
    subject: str
    status: TaskStatus
    owner: str | None = None
    blocked_by: list[str] = Field(default_factory=list)


class TaskListResult(BaseModel):
    tasks: list[TaskSummary]
    total: int


class TaskListConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class TaskList(
    BaseTool[TaskListArgs, TaskListResult, TaskListConfig, BaseToolState],
    ToolUIData[TaskListArgs, TaskListResult],
):
    description: ClassVar[str] = (
        "List all tasks in the persistent task list. Returns a brief summary "
        "(id, subject, status, owner, blockers) per task."
    )

    @classmethod
    def format_call_display(cls, args: TaskListArgs) -> ToolCallDisplay:
        return ToolCallDisplay(summary="TaskList")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, TaskListResult):
            return ToolResultDisplay(
                success=True, message=f"{event.result.total} task(s)"
            )
        return ToolResultDisplay(success=True, message="OK")

    @classmethod
    def get_status_text(cls) -> str:
        return "Listing tasks"

    async def run(
        self, args: TaskListArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | TaskListResult, None]:
        store = get_default_store()
        tasks = store.list(include_deleted=args.include_deleted)
        yield TaskListResult(
            tasks=[
                TaskSummary(
                    id=t.id,
                    subject=t.subject,
                    status=t.status,
                    owner=t.owner,
                    blocked_by=t.blocked_by,
                )
                for t in tasks
            ],
            total=len(tasks),
        )


class TaskUpdateArgs(BaseModel):
    task_id: str = Field(description="ID of the task to update.")
    subject: str | None = None
    description: str | None = None
    active_form: str | None = None
    status: TaskStatus | None = None
    owner: str | None = None
    add_blocked_by: list[str] | None = None
    add_blocks: list[str] | None = None
    metadata: dict[str, Any] | None = None


class TaskUpdateResult(BaseModel):
    id: str
    subject: str
    status: TaskStatus
    message: str = ""


class TaskUpdateConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class TaskUpdate(
    BaseTool[TaskUpdateArgs, TaskUpdateResult, TaskUpdateConfig, BaseToolState],
    ToolUIData[TaskUpdateArgs, TaskUpdateResult],
):
    description: ClassVar[str] = (
        "Update a task: change its status (pending/in_progress/completed/deleted), "
        "subject, description, owner, or dependencies."
    )

    @classmethod
    def format_call_display(cls, args: TaskUpdateArgs) -> ToolCallDisplay:
        bits = [f"TaskUpdate {args.task_id}"]
        if args.status:
            bits.append(f"-> {args.status}")
        return ToolCallDisplay(summary=" ".join(bits))

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, TaskUpdateResult):
            return ToolResultDisplay(success=True, message=event.result.message)
        return ToolResultDisplay(success=True, message="Updated")

    @classmethod
    def get_status_text(cls) -> str:
        return "Updating task"

    async def run(
        self, args: TaskUpdateArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | TaskUpdateResult, None]:
        store = get_default_store()
        try:
            task = store.update(
                args.task_id,
                subject=args.subject,
                description=args.description,
                active_form=args.active_form,
                status=args.status,
                owner=args.owner,
                add_blocked_by=args.add_blocked_by,
                add_blocks=args.add_blocks,
                metadata=args.metadata,
            )
        except KeyError as exc:
            raise ToolError(f"Task not found: {exc}") from exc
        yield TaskUpdateResult(
            id=task.id,
            subject=task.subject,
            status=task.status,
            message=f"Task {task.id} updated",
        )


class TaskOutputArgs(BaseModel):
    task_id: str = Field(description="ID of the task to read/write output.")
    output: str | None = Field(
        default=None,
        description="If provided, sets the task output text. Otherwise reads it.",
    )


class TaskOutputResult(BaseModel):
    task_id: str
    output: str
    written: bool


class TaskOutputConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class TaskOutput(
    BaseTool[TaskOutputArgs, TaskOutputResult, TaskOutputConfig, BaseToolState],
    ToolUIData[TaskOutputArgs, TaskOutputResult],
):
    description: ClassVar[str] = (
        "Read or write the stored output text of a task. Pass `output` to set it, "
        "omit `output` to read the current value (e.g., to fetch a completed "
        "sub-agent's report)."
    )

    @classmethod
    def format_call_display(cls, args: TaskOutputArgs) -> ToolCallDisplay:
        verb = "write" if args.output is not None else "read"
        return ToolCallDisplay(summary=f"TaskOutput {args.task_id} ({verb})")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, TaskOutputResult):
            verb = "Wrote" if event.result.written else "Read"
            return ToolResultDisplay(
                success=True, message=f"{verb} task {event.result.task_id} output"
            )
        return ToolResultDisplay(success=True, message="OK")

    @classmethod
    def get_status_text(cls) -> str:
        return "Reading task output"

    async def run(
        self, args: TaskOutputArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | TaskOutputResult, None]:
        store = get_default_store()
        if args.output is not None:
            try:
                task = store.set_output(args.task_id, args.output)
            except KeyError as exc:
                raise ToolError(f"Task not found: {exc}") from exc
            yield TaskOutputResult(task_id=task.id, output=task.output, written=True)
            return
        task = store.get(args.task_id)
        if task is None:
            raise ToolError(f"Task not found: {args.task_id}")
        yield TaskOutputResult(task_id=task.id, output=task.output, written=False)


class TaskStopArgs(BaseModel):
    task_id: str = Field(description="ID of the task to stop.")
    reason: str | None = Field(
        default=None, description="Optional reason for stopping."
    )


class TaskStopResult(BaseModel):
    task_id: str
    message: str
    previous_status: TaskStatus
    new_status: TaskStatus


class TaskStopConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class TaskStop(
    BaseTool[TaskStopArgs, TaskStopResult, TaskStopConfig, BaseToolState],
    ToolUIData[TaskStopArgs, TaskStopResult],
):
    description: ClassVar[str] = (
        "Stop a task: marks it completed (or deleted, depending on context). Used to "
        "halt background or in-progress tasks."
    )

    @classmethod
    def format_call_display(cls, args: TaskStopArgs) -> ToolCallDisplay:
        return ToolCallDisplay(summary=f"TaskStop {args.task_id}")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, TaskStopResult):
            return ToolResultDisplay(success=True, message=event.result.message)
        return ToolResultDisplay(success=True, message="Stopped")

    @classmethod
    def get_status_text(cls) -> str:
        return "Stopping task"

    async def run(
        self, args: TaskStopArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | TaskStopResult, None]:
        store = get_default_store()
        task = store.get(args.task_id)
        if task is None:
            raise ToolError(f"Task not found: {args.task_id}")
        prev = task.status
        new_status = TaskStatus.COMPLETED
        store.update(args.task_id, status=new_status)
        suffix = f" — {args.reason}" if args.reason else ""
        yield TaskStopResult(
            task_id=args.task_id,
            previous_status=prev,
            new_status=new_status,
            message=f"Stopped task {args.task_id} ({prev} -> {new_status}){suffix}",
        )
