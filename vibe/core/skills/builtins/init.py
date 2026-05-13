from __future__ import annotations

from vibe.core.skills.models import SkillInfo

SKILL = SkillInfo(
    name="init",
    description=(
        "Initialize a new AGENTS.md (or CLAUDE.md) file documenting the codebase. "
        "Surveys the project structure, identifies the tech stack, key directories, "
        "build/test commands, and conventions, then writes a concise primer for "
        "future agents."
    ),
    user_invocable=True,
    prompt="""# /init — Initialize AGENTS.md

You are creating an `AGENTS.md` file at the root of the current working directory.
This file will be read by future agent sessions so they can quickly orient themselves
in the codebase.

## Procedure

1. **Survey** the repository layout. Use `glob` and `read_file` to:
   - List top-level directories and files
   - Read `README.md`, `pyproject.toml` / `package.json` / `Cargo.toml` / `go.mod` etc.
   - Identify the test runner and how tests are invoked
   - Note any obvious build commands (Makefile, scripts/, justfile)
   - Identify the language(s) and key frameworks

2. **Detect conventions**:
   - Linter / formatter config (`.ruff.toml`, `.eslintrc`, `.prettierrc`)
   - Pre-commit hooks
   - Test layout (where do tests live, what naming pattern)
   - Branching / commit conventions if visible (CHANGELOG, CONTRIBUTING.md)

3. **Write the file** to `AGENTS.md` at the repo root with these sections:
   - **Project**: One-line description
   - **Tech stack**: Language, framework, key libraries
   - **Layout**: Tree of top 2 levels with one-line annotations
   - **Run / build / test**: Commands to install deps, run dev, run tests
   - **Conventions**: Linter, formatter, commit style, anything notable
   - **Things to know**: Gotchas, things future agents should not break

   Keep it under ~150 lines. Concise, scannable, factual. Do not include marketing
   language or fluff.

4. **Confirm** to the user that AGENTS.md was created and offer to also create a
   matching CLAUDE.md (a copy or symlink for Claude Code compatibility).

If an AGENTS.md already exists, read it first and ask the user whether to
overwrite or update only certain sections.
""",
)
