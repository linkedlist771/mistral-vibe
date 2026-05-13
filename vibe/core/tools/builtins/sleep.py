from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import ClassVar

from pydantic import BaseModel, Field

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


class SleepArgs(BaseModel):
    milliseconds: int = Field(
        description="Number of milliseconds to sleep (max 60000 = 60s)",
        ge=1,
        le=60000,
    )
    reason: str | None = Field(
        default=None,
        description="Optional short reason describing why you're sleeping (for telemetry).",
    )


class SleepResult(BaseModel):
    slept_ms: int
    reason: str | None = None


class SleepConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS
    max_ms: int = 60000


class SleepState(BaseToolState):
    pass


class Sleep(
    BaseTool[SleepArgs, SleepResult, SleepConfig, SleepState],
    ToolUIData[SleepArgs, SleepResult],
):
    description: ClassVar[str] = (
        "Pause execution for a specified number of milliseconds. Use sparingly — "
        "prefer polling or event-driven waits. Useful when you need a deterministic "
        "delay (e.g., waiting for a process to start). Max 60 seconds per call."
    )

    @classmethod
    def format_call_display(cls, args: SleepArgs) -> ToolCallDisplay:
        s = f"Sleeping {args.milliseconds}ms"
        if args.reason:
            s += f" ({args.reason})"
        return ToolCallDisplay(summary=s)

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, SleepResult):
            return ToolResultDisplay(success=True, message="Slept")
        return ToolResultDisplay(success=True, message=f"Slept {event.result.slept_ms}ms")

    @classmethod
    def get_status_text(cls) -> str:
        return "Sleeping"

    async def run(
        self, args: SleepArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | SleepResult, None]:
        if args.milliseconds > self.config.max_ms:
            raise ToolError(
                f"Refusing to sleep {args.milliseconds}ms (max {self.config.max_ms}ms)"
            )
        await asyncio.sleep(args.milliseconds / 1000.0)
        yield SleepResult(slept_ms=args.milliseconds, reason=args.reason)
