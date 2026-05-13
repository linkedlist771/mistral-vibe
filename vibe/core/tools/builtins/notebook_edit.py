from __future__ import annotations

from collections.abc import AsyncGenerator
import json
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


CellType = Literal["code", "markdown", "raw"]
EditMode = Literal["replace", "insert", "delete"]


class NotebookEditArgs(BaseModel):
    notebook_path: str = Field(
        description="Absolute path to the .ipynb file to edit."
    )
    new_source: str | None = Field(
        default=None,
        description=(
            "New source content for the cell. Required when edit_mode is "
            "'replace' or 'insert'. Ignored when edit_mode is 'delete'."
        ),
    )
    cell_id: str | None = Field(
        default=None,
        description=(
            "ID of the cell to edit. Optional for 'insert' (cell is inserted "
            "after this cell, or at the start if not given)."
        ),
    )
    cell_type: CellType | None = Field(
        default=None,
        description="Cell type: 'code', 'markdown', or 'raw'. Required for 'insert'.",
    )
    edit_mode: EditMode = Field(
        default="replace",
        description="How to edit the cell: 'replace' (default), 'insert', or 'delete'.",
    )


class NotebookEditResult(BaseModel):
    notebook_path: str
    edit_mode: EditMode
    cell_id: str | None = None
    cell_count: int = 0
    message: str = ""


class NotebookEditConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK


class NotebookEditState(BaseToolState):
    pass


def _ensure_cell_id(cell: dict, index: int) -> str:
    cell_id = cell.get("id")
    if not cell_id:
        cell_id = f"cell-{index}"
        cell["id"] = cell_id
    return cell_id


def _make_cell(cell_type: CellType, source: str, cell_id: str) -> dict:
    base: dict = {
        "cell_type": cell_type,
        "id": cell_id,
        "metadata": {},
        "source": source.splitlines(keepends=True) if source else [],
    }
    if cell_type == "code":
        base["execution_count"] = None
        base["outputs"] = []
    return base


class NotebookEdit(
    BaseTool[NotebookEditArgs, NotebookEditResult, NotebookEditConfig, NotebookEditState],
    ToolUIData[NotebookEditArgs, NotebookEditResult],
):
    description: ClassVar[str] = (
        "Edit cells in a Jupyter notebook (.ipynb). Supports three modes: "
        "'replace' an existing cell's source, 'insert' a new cell after a given "
        "cell_id (or at the start), or 'delete' a cell by cell_id."
    )

    @classmethod
    def format_call_display(cls, args: NotebookEditArgs) -> ToolCallDisplay:
        return ToolCallDisplay(
            summary=f"NotebookEdit {Path(args.notebook_path).name} ({args.edit_mode})"
        )

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, NotebookEditResult):
            return ToolResultDisplay(success=True, message="OK")
        return ToolResultDisplay(success=True, message=event.result.message)

    @classmethod
    def get_status_text(cls) -> str:
        return "Editing notebook"

    async def run(
        self, args: NotebookEditArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | NotebookEditResult, None]:
        path = Path(args.notebook_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            raise ToolError(f"Notebook does not exist: {path}")
        if path.suffix != ".ipynb":
            raise ToolError(f"Not a Jupyter notebook (.ipynb): {path}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ToolError(f"Notebook is not valid JSON: {exc}") from exc

        cells = data.setdefault("cells", [])
        for idx, c in enumerate(cells):
            _ensure_cell_id(c, idx)

        mode = args.edit_mode
        message = ""
        result_cell_id = args.cell_id

        if mode == "replace":
            if not args.cell_id:
                raise ToolError("cell_id is required for replace mode")
            if args.new_source is None:
                raise ToolError("new_source is required for replace mode")
            for cell in cells:
                if cell.get("id") == args.cell_id:
                    cell["source"] = (
                        args.new_source.splitlines(keepends=True)
                        if args.new_source
                        else []
                    )
                    if args.cell_type:
                        cell["cell_type"] = args.cell_type
                    message = f"Replaced cell {args.cell_id}"
                    break
            else:
                raise ToolError(f"Cell not found: {args.cell_id}")

        elif mode == "insert":
            if args.new_source is None:
                raise ToolError("new_source is required for insert mode")
            if not args.cell_type:
                raise ToolError("cell_type is required for insert mode")
            new_cell_id = f"cell-new-{len(cells)}"
            new_cell = _make_cell(args.cell_type, args.new_source, new_cell_id)
            if args.cell_id:
                inserted = False
                for idx, c in enumerate(cells):
                    if c.get("id") == args.cell_id:
                        cells.insert(idx + 1, new_cell)
                        inserted = True
                        break
                if not inserted:
                    raise ToolError(f"Cell not found: {args.cell_id}")
            else:
                cells.insert(0, new_cell)
            result_cell_id = new_cell_id
            message = f"Inserted new {args.cell_type} cell {new_cell_id}"

        elif mode == "delete":
            if not args.cell_id:
                raise ToolError("cell_id is required for delete mode")
            before = len(cells)
            cells[:] = [c for c in cells if c.get("id") != args.cell_id]
            if len(cells) == before:
                raise ToolError(f"Cell not found: {args.cell_id}")
            message = f"Deleted cell {args.cell_id}"
        else:
            raise ToolError(f"Unknown edit_mode: {mode}")

        path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

        yield NotebookEditResult(
            notebook_path=str(path),
            edit_mode=mode,
            cell_id=result_cell_id,
            cell_count=len(cells),
            message=message,
        )
