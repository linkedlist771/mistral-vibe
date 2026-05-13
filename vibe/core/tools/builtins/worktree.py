"""Worktree tools: enter_worktree / exit_worktree.

These wrap `git worktree` so an agent can work on an isolated copy of the repo
without disturbing the user's main checkout.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import os
from pathlib import Path
from typing import ClassVar, Literal

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


async def _run_git(cwd: Path, *args: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_b, err_b = await proc.communicate()
    return proc.returncode or 0, out_b.decode("utf-8", errors="replace"), err_b.decode(
        "utf-8", errors="replace"
    )


class EnterWorktreeArgs(BaseModel):
    name: str = Field(
        description="Short name for the worktree (used as branch + dirname)."
    )
    base_branch: str | None = Field(
        default=None,
        description="Branch to base the worktree on (default: current HEAD).",
    )
    path: str | None = Field(
        default=None,
        description=(
            "Optional path for the worktree directory. Defaults to a sibling "
            "directory '.vibe-worktrees/<name>'."
        ),
    )


class WorktreeResult(BaseModel):
    name: str
    path: str
    branch: str
    message: str = ""


class EnterWorktreeConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK


class EnterWorktree(
    BaseTool[EnterWorktreeArgs, WorktreeResult, EnterWorktreeConfig, BaseToolState],
    ToolUIData[EnterWorktreeArgs, WorktreeResult],
):
    description: ClassVar[str] = (
        "Create a git worktree for isolated work. The current process does NOT "
        "switch into it — the path is returned so subsequent tool calls can "
        "operate inside it. Branch is created from base_branch or HEAD."
    )

    @classmethod
    def format_call_display(cls, args: EnterWorktreeArgs) -> ToolCallDisplay:
        return ToolCallDisplay(summary=f"EnterWorktree {args.name}")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, WorktreeResult):
            return ToolResultDisplay(success=True, message=event.result.message)
        return ToolResultDisplay(success=True, message="OK")

    @classmethod
    def get_status_text(cls) -> str:
        return "Creating worktree"

    async def run(
        self, args: EnterWorktreeArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | WorktreeResult, None]:
        cwd = Path.cwd()
        rc, stdout, _ = await _run_git(cwd, "rev-parse", "--show-toplevel")
        if rc != 0:
            raise ToolError("Not inside a git repository")
        repo_root = Path(stdout.strip())

        base = args.base_branch
        if base is None:
            rc, head, _ = await _run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
            base = head.strip() if rc == 0 else "HEAD"

        wt_root = repo_root.parent / ".vibe-worktrees"
        wt_path = Path(args.path).expanduser().resolve() if args.path else wt_root / args.name
        wt_path.parent.mkdir(parents=True, exist_ok=True)

        branch = f"vibe/{args.name}"
        rc, _, err = await _run_git(
            repo_root, "worktree", "add", "-b", branch, str(wt_path), base
        )
        if rc != 0:
            raise ToolError(f"git worktree add failed: {err.strip()}")

        yield WorktreeResult(
            name=args.name,
            path=str(wt_path),
            branch=branch,
            message=f"Worktree '{args.name}' at {wt_path} (branch {branch})",
        )


class ExitWorktreeArgs(BaseModel):
    path: str = Field(description="Worktree path to remove.")
    action: Literal["keep", "remove"] = Field(
        default="remove",
        description="'remove' deletes the worktree directory; 'keep' just unregisters.",
    )
    discard_changes: bool = Field(
        default=False,
        description="If true, force-remove uncommitted changes.",
    )


class ExitWorktreeResult(BaseModel):
    path: str
    action: str
    message: str = ""


class ExitWorktreeConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK


class ExitWorktree(
    BaseTool[ExitWorktreeArgs, ExitWorktreeResult, ExitWorktreeConfig, BaseToolState],
    ToolUIData[ExitWorktreeArgs, ExitWorktreeResult],
):
    description: ClassVar[str] = (
        "Remove or unregister a previously-created git worktree. With "
        "`discard_changes=True`, uncommitted changes in the worktree are "
        "force-discarded; otherwise the removal fails on dirty trees."
    )

    @classmethod
    def format_call_display(cls, args: ExitWorktreeArgs) -> ToolCallDisplay:
        return ToolCallDisplay(summary=f"ExitWorktree {args.path}")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, ExitWorktreeResult):
            return ToolResultDisplay(success=True, message=event.result.message)
        return ToolResultDisplay(success=True, message="OK")

    @classmethod
    def get_status_text(cls) -> str:
        return "Removing worktree"

    async def run(
        self, args: ExitWorktreeArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | ExitWorktreeResult, None]:
        wt_path = Path(args.path).expanduser().resolve()
        rc, stdout, _ = await _run_git(wt_path, "rev-parse", "--show-toplevel")
        if rc != 0:
            raise ToolError("Worktree path is not inside a git repo")
        repo_root = Path(stdout.strip())

        flags = ["worktree", "remove", str(wt_path)]
        if args.discard_changes:
            flags.insert(2, "--force")
        if args.action == "keep":
            flags = ["worktree", "prune"]

        rc, _, err = await _run_git(repo_root, *flags)
        if rc != 0:
            raise ToolError(f"git worktree {args.action} failed: {err.strip()}")

        yield ExitWorktreeResult(
            path=str(wt_path),
            action=args.action,
            message=f"Worktree {args.action} at {wt_path}",
        )
