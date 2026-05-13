from __future__ import annotations

from vibe.core.skills.models import SkillInfo

SKILL = SkillInfo(
    name="pr",
    description=(
        "Create a pull request via `gh pr create`. Inspects the branch's commit "
        "history to produce a clear title and summary, then pushes and opens the "
        "PR."
    ),
    user_invocable=True,
    prompt="""# /pr — Create a pull request

You are opening a pull request for the current branch.

## Procedure

1. Gather context in parallel:
   - `git status`
   - `git log <default-branch>..HEAD --oneline`
   - `git diff <default-branch>...HEAD`
   - `git branch --show-current` and check whether it tracks a remote

2. Analyze ALL commits going into the PR — not just the latest. Many PRs
   include several commits; the description should summarize the full set.

3. Draft:
   - **Title** under 70 characters. Use the description body for details.
   - **Body** with sections:
     - `## Summary` — 1-3 bullets
     - `## Test plan` — what was verified / what to test

4. Push to remote if needed (`git push -u origin <branch>`).

5. Run `gh pr create --title "..." --body "$(cat <<'EOF' ... EOF)"` using a
   heredoc so the body keeps its formatting.

6. Return the PR URL to the user.

## Safety

- NEVER force-push to the default branch.
- If the branch is already pushed and up-to-date, skip the push step.
- Confirm the base branch with the user if it's anything other than `main`
  or `master`.
""",
)
