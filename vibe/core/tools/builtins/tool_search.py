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


class ToolSearchArgs(BaseModel):
    query: str = Field(
        description=(
            "Query to find tools. Use 'select:<tool_name>' (or "
            "'select:Tool1,Tool2') to fetch tools by exact name. Otherwise, "
            "tools are ranked by keyword overlap with name and description."
        )
    )
    max_results: int = Field(default=5, description="Maximum results to return (1-20).", ge=1, le=20)


class ToolMatch(BaseModel):
    name: str
    description: str
    score: float = 0.0


class ToolSearchResult(BaseModel):
    matches: list[ToolMatch]
    query: str
    total_searched: int = 0


class ToolSearchConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class ToolSearchState(BaseToolState):
    pass


def _score(query_words: set[str], text: str) -> float:
    if not query_words:
        return 0.0
    tl = text.lower()
    overlap = sum(1 for w in query_words if w in tl)
    return overlap / len(query_words)


class ToolSearch(
    BaseTool[ToolSearchArgs, ToolSearchResult, ToolSearchConfig, ToolSearchState],
    ToolUIData[ToolSearchArgs, ToolSearchResult],
):
    description: ClassVar[str] = (
        "Search the available tools registry by keywords or fetch tool schemas by name. "
        "Use 'select:Bash,Read' for direct selection. Use keywords like 'edit file' to "
        "find related tools. Returns name, description, and relevance score."
    )

    @classmethod
    def format_call_display(cls, args: ToolSearchArgs) -> ToolCallDisplay:
        return ToolCallDisplay(summary=f"ToolSearch '{args.query}'")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, ToolSearchResult):
            return ToolResultDisplay(success=True, message="Searched tools")
        r = event.result
        return ToolResultDisplay(
            success=True, message=f"Found {len(r.matches)} matching tool(s)"
        )

    @classmethod
    def get_status_text(cls) -> str:
        return "Searching tools"

    async def run(
        self, args: ToolSearchArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | ToolSearchResult, None]:
        tool_classes: dict[str, type] = {}
        try:
            from vibe.core.tools.builtins import (
                ask_user_question,
                bash,
                exit_plan_mode,
                glob as glob_mod,
                grep,
                notebook_edit,
                read_file,
                search_replace,
                skill,
                sleep as sleep_mod,
                task,
                todo,
                webfetch,
                websearch,
                write_file,
            )

            modules = [
                ask_user_question, bash, exit_plan_mode, glob_mod, grep,
                notebook_edit, read_file, search_replace, skill, sleep_mod,
                task, todo, webfetch, websearch, write_file,
            ]
            from vibe.core.tools.base import BaseTool as BT
            import inspect
            for mod in modules:
                for obj in vars(mod).values():
                    if not inspect.isclass(obj):
                        continue
                    if not issubclass(obj, BT) or obj is BT:
                        continue
                    if inspect.isabstract(obj):
                        continue
                    name = obj.get_name()
                    if name not in tool_classes:
                        tool_classes[name] = obj
        except Exception:
            pass

        query = args.query.strip()
        matches: list[ToolMatch] = []

        if query.lower().startswith("select:"):
            wanted = [
                w.strip().lower() for w in query.split(":", 1)[1].split(",") if w.strip()
            ]
            for w in wanted:
                cls = tool_classes.get(w)
                if cls is None:
                    continue
                matches.append(
                    ToolMatch(
                        name=cls.get_name(),
                        description=cls.description,
                        score=1.0,
                    )
                )
        else:
            words = {w.lower() for w in query.split() if w}
            for name, cls in tool_classes.items():
                text = f"{name} {cls.description}"
                s = _score(words, text)
                if s > 0:
                    matches.append(
                        ToolMatch(name=name, description=cls.description, score=s)
                    )
            matches.sort(key=lambda m: m.score, reverse=True)
            matches = matches[: args.max_results]

        yield ToolSearchResult(
            matches=matches, query=query, total_searched=len(tool_classes)
        )
