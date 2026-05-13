from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
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


class GlobArgs(BaseModel):
    pattern: str = Field(
        description=(
            "Glob pattern to match files. Supports wildcards (*, **, ?), character "
            "classes ([abc]), and brace expansion is NOT supported. Use ** for "
            "recursive matching across directories. Examples: '**/*.py', "
            "'src/**/*.{ts,tsx}' (NOT supported, list separately), 'tests/test_*.py'."
        )
    )
    path: str | None = Field(
        default=None,
        description=(
            "The directory to search in. Defaults to the current working directory. "
            "Must be an absolute path or relative to the working directory."
        ),
    )
    case_sensitive: bool = Field(
        default=False,
        description="Whether to match case-sensitively. Defaults to False.",
    )
    limit: int = Field(
        default=200,
        description="Maximum number of results to return (default 200, max 1000).",
        ge=1,
        le=1000,
    )


class GlobMatch(BaseModel):
    path: str
    is_dir: bool = False
    mtime: float = 0.0


class GlobResult(BaseModel):
    matches: list[GlobMatch]
    truncated: bool = False
    total_found: int = 0
    pattern: str
    base_path: str


class GlobConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class GlobState(BaseToolState):
    pass


class Glob(
    BaseTool[GlobArgs, GlobResult, GlobConfig, GlobState],
    ToolUIData[GlobArgs, GlobResult],
):
    description: ClassVar[str] = (
        "Find files matching a glob pattern. Fast file pattern matching that works "
        "with any codebase size. Supports patterns like '**/*.py', 'src/*.ts'. "
        "Returns matching file paths sorted by modification time (newest first). "
        "Use this when you need to find files by name pattern. Use Grep for content "
        "search instead."
    )

    @classmethod
    def format_call_display(cls, args: GlobArgs) -> ToolCallDisplay:
        loc = args.path or "."
        return ToolCallDisplay(summary=f"Glob {args.pattern} in {loc}")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, GlobResult):
            return ToolResultDisplay(success=True, message="Success")
        r = event.result
        msg = f"Found {len(r.matches)} match(es)"
        if r.truncated:
            msg += f" (truncated from {r.total_found})"
        return ToolResultDisplay(success=True, message=msg)

    @classmethod
    def get_status_text(cls) -> str:
        return "Searching for files"

    async def run(
        self, args: GlobArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | GlobResult, None]:
        base = Path(args.path) if args.path else Path.cwd()
        base = base.expanduser().resolve()
        if not base.exists():
            raise ToolError(f"Path does not exist: {base}")
        if not base.is_dir():
            raise ToolError(f"Path is not a directory: {base}")

        pattern = args.pattern
        try:
            if args.case_sensitive:
                raw_matches = list(base.glob(pattern))
            else:
                raw_matches = list(base.glob(pattern, case_sensitive=False))
        except (ValueError, OSError) as exc:
            raise ToolError(f"Invalid glob pattern '{pattern}': {exc}") from exc

        items: list[GlobMatch] = []
        for p in raw_matches:
            try:
                stat = p.stat()
                items.append(
                    GlobMatch(
                        path=str(p),
                        is_dir=p.is_dir(),
                        mtime=stat.st_mtime,
                    )
                )
            except OSError:
                continue

        items.sort(key=lambda m: m.mtime, reverse=True)
        total = len(items)
        truncated = total > args.limit
        items = items[: args.limit]

        yield GlobResult(
            matches=items,
            truncated=truncated,
            total_found=total,
            pattern=pattern,
            base_path=str(base),
        )
