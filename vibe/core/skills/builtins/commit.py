from __future__ import annotations

from vibe.core.skills.models import SkillInfo

SKILL = SkillInfo(
    name="commit",
    description=(
        "Create a git commit for the currently staged + unstaged changes, following "
        "the repository's commit message style. Inspects git history to match tone "
        "and prefix conventions."
    ),
    user_invocable=True,
    prompt="""# /commit — Create a git commit

You are creating a git commit for the user.

## Procedure

1. Run, in parallel where possible:
   - `git status` (do NOT use `-uall` on large repos)
   - `git diff` (staged + unstaged)
   - `git log -n 10 --oneline` (to match the project's commit style)

2. Decide what to stage. **Prefer adding specific files by name** over
   `git add -A` — it's easy to accidentally include `.env`, credentials, or
   build artifacts. Warn the user before staging anything that looks sensitive.

3. Draft the commit message:
   - Match the project's style (Conventional Commits? plain prose? prefix
     tags like `feat:` / `fix:`?). Look at recent commits.
   - Subject under 70 characters, imperative mood ("Fix login bug", not "Fixed").
   - Focus on the **why** more than the **what** — the diff already shows what.
   - If the change touches multiple unrelated areas, suggest splitting into
     separate commits.

4. Show the user the proposed commit message and the files to be staged before
   running `git commit`.

5. After the commit, run `git status` to confirm.

## Safety rules

- NEVER pass `--no-verify` unless the user explicitly asks for it.
- NEVER amend a published commit unless the user explicitly asks.
- NEVER `git push` unless the user explicitly asks.
- If a pre-commit hook fails, fix the issue and create a NEW commit — never
  use `--amend` after a hook failure (the commit didn't happen yet).
""",
)
