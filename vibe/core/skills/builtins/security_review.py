from __future__ import annotations

from vibe.core.skills.models import SkillInfo

SKILL = SkillInfo(
    name="security-review",
    description=(
        "Security-focused review of the current branch. Looks for OWASP-class "
        "vulnerabilities (injection, XSS, SSRF, auth/authz gaps, secret leakage, "
        "unsafe deserialization, path traversal, race conditions) plus supply-chain "
        "risks introduced by new dependencies."
    ),
    user_invocable=True,
    prompt="""# /security-review — Security audit of pending changes

You are doing a security review of the changes on the current branch.

## Scope

1. Establish what's changing: `git diff main...HEAD` and any uncommitted edits.
2. Read full files for every changed source file. Don't review from the diff
   alone — security bugs often hide in the unchanged code around the change.

## Categories to check

For each, point to specific files and lines:

- **Injection** — SQL, NoSQL, OS command, LDAP, template, XPath. Look for string
  concatenation into queries/commands and unvalidated input flowing into parsers.
- **Cross-site scripting** — Unescaped output in HTML, dangerous innerHTML /
  dangerouslySetInnerHTML, missing CSP.
- **Authentication / authorization** — Missing auth checks on new endpoints,
  IDOR (acting on resources without ownership check), session fixation,
  unsigned cookies, weak password handling.
- **SSRF / open redirect** — User-controlled URLs going into fetch/requests
  without allowlisting; redirects to user-provided locations.
- **Path traversal** — User-controlled paths reaching filesystem APIs without
  normalization or jail.
- **Deserialization** — pickle.loads, yaml.load (not safe_load), eval, exec,
  marshalling untrusted data.
- **Secrets** — Hardcoded keys, tokens in code, accidental .env commits, secrets
  in logs.
- **Race conditions** — TOCTOU, missing locks on shared mutable state.
- **Crypto** — Custom crypto, weak algorithms (MD5/SHA1 for security), missing
  IV randomness, ECB mode, hardcoded keys, missing constant-time compare.
- **Supply chain** — New dependencies added. Are they reputable? Any typosquats?
  Anything pinned to a non-semver range?
- **Network exposure** — New ports opened, services bound to 0.0.0.0 without
  intent, debug interfaces left on.

## Output

Group findings by severity:

- **Critical** — Exploitable now; fix before merge.
- **High** — Likely exploitable in some configuration; fix before release.
- **Medium** — Risky pattern; refactor recommended.
- **Low / Informational** — Defense-in-depth suggestions.

For each finding give: file:line, what's wrong, how it could be exploited,
suggested fix.

Conclude with: blocker / non-blocking / no issues found.

Do NOT modify code unless the user asks you to fix afterward.
""",
)
