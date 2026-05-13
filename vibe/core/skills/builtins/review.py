from __future__ import annotations

from vibe.core.skills.models import SkillInfo

SKILL = SkillInfo(
    name="review",
    description=(
        "Review the current branch / pending changes (uncommitted + commits not on main). "
        "Acts as an independent reviewer: checks correctness, readability, test coverage, "
        "and surfaces concrete issues with file:line references."
    ),
    user_invocable=True,
    prompt="""# /review — Review pending changes

You are doing an independent code review of the current branch.

## Procedure

1. Establish scope:
   - `git status` for uncommitted changes
   - `git log main..HEAD --oneline` (or default branch) for branch commits
   - `git diff main...HEAD` for the cumulative diff vs main

2. For each changed file, read the *whole file* (not just the diff hunk) so you
   understand the change in context. Don't review based on the diff alone — the
   diff hides what's around it.

3. Produce a structured review with these sections (omit sections that have no
   findings):

   - **Summary** — 2-3 sentences on what this branch does.
   - **Correctness** — Bugs, edge cases, type errors, off-by-ones. Include
     file:line references.
   - **Design** — Architectural issues, abstraction leaks, places that should be
     simpler / less abstract.
   - **Tests** — Coverage gaps, missing edge-case tests, brittle tests.
   - **Style / readability** — Naming, comments, dead code, oversize functions.
   - **Risk to ship** — Anything blocking, with severity (blocker / important / nit).

4. Be specific. "Consider error handling" is useless feedback. "src/foo.py:42 — this
   raises FileNotFoundError but the caller in bar.py:11 catches Exception, which
   will silently mask other errors" is useful feedback.

5. Conclude with a recommendation: ship / ship with nits / needs changes /
   rework.

Do NOT modify files unless the user asks you to fix the issues afterward.
""",
)
