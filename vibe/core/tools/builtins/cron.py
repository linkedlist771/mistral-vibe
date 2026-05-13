"""Cron tools: cron_create, cron_list, cron_delete.

These persist scheduled tasks to ~/.vibe/cron.json. A separate runner process can
later pick them up; this module just provides the CRUD interface used by the
agent. (Mirrors Claude Code's CronCreate/CronList/CronDelete tools.)
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
import json
from pathlib import Path
import threading
from typing import Any, ClassVar
import uuid

from pydantic import BaseModel, Field

from vibe.core.paths import VIBE_HOME
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


_LOCK = threading.Lock()


def _cron_file() -> Path:
    return Path(VIBE_HOME.path) / "cron.json"


def _load() -> dict[str, Any]:
    p = _cron_file()
    if not p.exists():
        return {"jobs": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"jobs": []}


def _save(data: dict[str, Any]) -> None:
    p = _cron_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


class CronJob(BaseModel):
    id: str
    schedule: str  # cron expression or interval like "5m"
    prompt: str
    recurring: bool = True
    durable: bool = True
    created_at: str = ""
    last_run: str | None = None
    next_run: str | None = None


class CronCreateArgs(BaseModel):
    schedule: str = Field(
        description=(
            "When to run. Either a cron expression ('0 9 * * *') or interval "
            "shorthand ('5m', '1h', '30s')."
        )
    )
    prompt: str = Field(description="Prompt to run when the cron fires.")
    recurring: bool = Field(
        default=True, description="Run repeatedly (True) or just once (False)."
    )
    durable: bool = Field(
        default=True, description="Survive process restarts (default True)."
    )


class CronCreateResult(BaseModel):
    job_id: str
    schedule: str
    message: str


class CronCreateConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK


class CronCreate(
    BaseTool[CronCreateArgs, CronCreateResult, CronCreateConfig, BaseToolState],
    ToolUIData[CronCreateArgs, CronCreateResult],
):
    description: ClassVar[str] = (
        "Schedule a recurring or one-shot task. The job is stored on disk and "
        "fired by the vibe scheduler when its time comes. Use 'interval' shorthand "
        "('5m', '2h') for simple recurrences."
    )

    @classmethod
    def format_call_display(cls, args: CronCreateArgs) -> ToolCallDisplay:
        return ToolCallDisplay(summary=f"CronCreate {args.schedule}")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, CronCreateResult):
            return ToolResultDisplay(success=True, message=event.result.message)
        return ToolResultDisplay(success=True, message="Scheduled")

    @classmethod
    def get_status_text(cls) -> str:
        return "Scheduling cron"

    async def run(
        self, args: CronCreateArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | CronCreateResult, None]:
        with _LOCK:
            data = _load()
            job = CronJob(
                id=str(uuid.uuid4())[:8],
                schedule=args.schedule,
                prompt=args.prompt,
                recurring=args.recurring,
                durable=args.durable,
                created_at=datetime.now(UTC).isoformat(),
            )
            data["jobs"].append(job.model_dump(mode="json"))
            _save(data)
        yield CronCreateResult(
            job_id=job.id,
            schedule=args.schedule,
            message=f"Scheduled cron {job.id} ({args.schedule})",
        )


class CronListArgs(BaseModel):
    pass


class CronListResult(BaseModel):
    jobs: list[CronJob]
    total: int


class CronListConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class CronList(
    BaseTool[CronListArgs, CronListResult, CronListConfig, BaseToolState],
    ToolUIData[CronListArgs, CronListResult],
):
    description: ClassVar[str] = "List all scheduled cron jobs."

    @classmethod
    def format_call_display(cls, args: CronListArgs) -> ToolCallDisplay:
        return ToolCallDisplay(summary="CronList")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, CronListResult):
            return ToolResultDisplay(
                success=True, message=f"{event.result.total} job(s)"
            )
        return ToolResultDisplay(success=True, message="OK")

    @classmethod
    def get_status_text(cls) -> str:
        return "Listing crons"

    async def run(
        self, args: CronListArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | CronListResult, None]:
        with _LOCK:
            data = _load()
        jobs = [CronJob.model_validate(j) for j in data.get("jobs", [])]
        yield CronListResult(jobs=jobs, total=len(jobs))


class CronDeleteArgs(BaseModel):
    job_id: str = Field(description="Id of the cron job to remove.")


class CronDeleteResult(BaseModel):
    job_id: str
    removed: bool
    message: str


class CronDeleteConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK


class CronDelete(
    BaseTool[CronDeleteArgs, CronDeleteResult, CronDeleteConfig, BaseToolState],
    ToolUIData[CronDeleteArgs, CronDeleteResult],
):
    description: ClassVar[str] = "Delete a scheduled cron job by id."

    @classmethod
    def format_call_display(cls, args: CronDeleteArgs) -> ToolCallDisplay:
        return ToolCallDisplay(summary=f"CronDelete {args.job_id}")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, CronDeleteResult):
            return ToolResultDisplay(success=event.result.removed, message=event.result.message)
        return ToolResultDisplay(success=True, message="OK")

    @classmethod
    def get_status_text(cls) -> str:
        return "Deleting cron"

    async def run(
        self, args: CronDeleteArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | CronDeleteResult, None]:
        with _LOCK:
            data = _load()
            before = len(data.get("jobs", []))
            data["jobs"] = [j for j in data.get("jobs", []) if j.get("id") != args.job_id]
            removed = len(data["jobs"]) < before
            if removed:
                _save(data)
        if not removed:
            raise ToolError(f"Cron job not found: {args.job_id}")
        yield CronDeleteResult(
            job_id=args.job_id, removed=True, message=f"Deleted cron {args.job_id}"
        )
