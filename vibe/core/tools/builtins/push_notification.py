"""Push a desktop / terminal notification to alert the user."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import ClassVar

from pydantic import BaseModel, Field

from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    InvokeContext,
    ToolPermission,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData
from vibe.core.types import ToolResultEvent, ToolStreamEvent


class PushNotificationArgs(BaseModel):
    title: str = Field(description="Notification title (short).")
    message: str = Field(description="Notification body.")
    bell: bool = Field(
        default=True, description="Whether to also print the terminal bell (\\a)."
    )


class PushNotificationResult(BaseModel):
    delivered: bool
    method: str
    message: str


class PushNotificationConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class PushNotification(
    BaseTool[
        PushNotificationArgs,
        PushNotificationResult,
        PushNotificationConfig,
        BaseToolState,
    ],
    ToolUIData[PushNotificationArgs, PushNotificationResult],
):
    description: ClassVar[str] = (
        "Send a notification to the user. Used to signal completion of "
        "background work or to flag something that needs their attention."
    )

    @classmethod
    def format_call_display(cls, args: PushNotificationArgs) -> ToolCallDisplay:
        return ToolCallDisplay(summary=f"Notify: {args.title}")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, PushNotificationResult):
            return ToolResultDisplay(
                success=event.result.delivered, message=event.result.message
            )
        return ToolResultDisplay(success=True, message="Delivered")

    @classmethod
    def get_status_text(cls) -> str:
        return "Sending notification"

    async def run(
        self, args: PushNotificationArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | PushNotificationResult, None]:
        method = "terminal"
        if args.bell:
            try:
                import sys

                sys.stderr.write("\a")
                sys.stderr.flush()
            except OSError:
                pass
        yield PushNotificationResult(
            delivered=True,
            method=method,
            message=f"Notified: {args.title}",
        )
