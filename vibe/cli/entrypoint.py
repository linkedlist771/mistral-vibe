from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from rich import print as rprint

from vibe import __version__
from vibe.core.config.harness_files import init_harness_files_manager
from vibe.core.trusted_folders import find_trustable_files, trusted_folders_manager
from vibe.setup.trusted_folders.trust_folder_dialog import (
    TrustDialogQuitException,
    ask_trust_folder,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Claude Code (Python) interactive CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment variables:\n"
            "  VIBE_HOME       Override the Vibe home directory (default: ~/.vibe)\n"
            "  LOG_LEVEL       Logging level: DEBUG, INFO, WARNING (default), ERROR, CRITICAL.\n"
            "                  Logs are written to $VIBE_HOME/logs/vibe.log.\n"
            "  LOG_MAX_BYTES   Max size of vibe.log before rotation (default: 10485760).\n"
            "  VIBE_*          Override any config field (e.g. VIBE_ACTIVE_MODEL=local)."
        ),
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "initial_prompt",
        nargs="?",
        metavar="PROMPT",
        help="Initial prompt to start the interactive session with.",
    )
    parser.add_argument(
        "-p",
        "--prompt",
        "--print",
        nargs="?",
        const="",
        metavar="TEXT",
        help="Run in programmatic mode: send prompt, auto-approve all tools, "
        "output response, and exit. (--print is an alias for Claude Code parity.)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        metavar="N",
        help="Maximum number of assistant turns "
        "(only applies in programmatic mode with -p).",
    )
    parser.add_argument(
        "--max-price",
        type=float,
        metavar="DOLLARS",
        help="Maximum cost in dollars (only applies in programmatic mode with -p). "
        "Session will be interrupted if cost exceeds this limit.",
    )
    parser.add_argument(
        "--enabled-tools",
        "--allowed-tools",
        "--allowedTools",
        action="append",
        metavar="TOOL",
        dest="enabled_tools",
        help="Enable specific tools. In programmatic mode (-p), this disables "
        "all other tools. "
        "Can use exact names, glob patterns (e.g., 'bash*'), or "
        "regex with 're:' prefix. Can be specified multiple times. "
        "(--allowed-tools / --allowedTools are aliases for Claude Code parity.)",
    )
    parser.add_argument(
        "--disallowed-tools",
        "--disallowedTools",
        action="append",
        metavar="TOOL",
        dest="disallowed_tools",
        help="Disable specific tools. Same matching rules as --allowed-tools.",
    )
    parser.add_argument(
        "--output",
        "--output-format",
        type=str,
        choices=["text", "json", "streaming", "stream-json"],
        default="text",
        dest="output",
        help="Output format for programmatic mode (-p): 'text' "
        "for human-readable (default), 'json' for all messages at end, "
        "'streaming' / 'stream-json' for newline-delimited JSON per message.",
    )
    parser.add_argument(
        "--agent",
        metavar="NAME",
        default=None,
        help="Agent to use (builtin: default, plan, accept-edits, auto-approve, "
        "or custom from ~/.vibe/agents/NAME.toml). In interactive mode, "
        "defaults to the 'default_agent' config setting. In programmatic "
        "mode (-p/--prompt), defaults to auto-approve and 'default_agent' "
        "is ignored.",
    )
    parser.add_argument(
        "--permission-mode",
        choices=["default", "plan", "acceptEdits", "bypassPermissions", "auto"],
        default=None,
        dest="permission_mode",
        help="Claude Code-compatible permission mode. Mapped to vibe agents: "
        "default→default, plan→plan, acceptEdits→accept-edits, "
        "bypassPermissions/auto→auto-approve. Equivalent to using --agent "
        "with the corresponding name.",
    )
    parser.add_argument(
        "--dangerously-skip-permissions",
        action="store_true",
        dest="dangerously_skip_permissions",
        help="Bypass ALL tool permission checks. Equivalent to "
        "`--agent auto-approve`. Use only in trusted environments (Docker, "
        "sandbox, throwaway VMs); the agent can run arbitrary shell commands "
        "and edit any file without confirmation.",
    )
    parser.add_argument(
        "--model",
        metavar="ALIAS",
        default=None,
        help="Override the active model for this run (e.g. 'gpt-5.5(xhigh)'). "
        "Equivalent to VIBE_ACTIVE_MODEL=<alias>. Must match a [[models]] "
        "alias from .vibe/config.toml.",
    )
    parser.add_argument(
        "--add-dir",
        action="append",
        metavar="DIR",
        dest="add_dir",
        default=[],
        help="Trust an additional directory for this run. Can be specified "
        "multiple times. Useful when working on code spread across sibling "
        "repos.",
    )
    parser.add_argument(
        "--system-prompt",
        metavar="TEXT",
        default=None,
        dest="system_prompt",
        help="Override the default system prompt for this run.",
    )
    parser.add_argument(
        "--append-system-prompt",
        metavar="TEXT",
        default=None,
        dest="append_system_prompt",
        help="Append text to the default system prompt for this run.",
    )
    parser.add_argument("--setup", action="store_true", help="Setup API key and exit")
    parser.add_argument(
        "--workdir",
        type=Path,
        metavar="DIR",
        help="Change to this directory before running",
    )
    parser.add_argument(
        "--trust",
        action="store_true",
        help="Trust the working directory for this invocation only (not "
        "persisted to trusted_folders.toml). Skips the trust prompt. "
        "Use this for non-interactive automation.",
    )

    # Feature flag for teleport, not exposed to the user yet
    parser.add_argument("--teleport", action="store_true", help=argparse.SUPPRESS)

    continuation_group = parser.add_mutually_exclusive_group()
    continuation_group.add_argument(
        "-c",
        "--continue",
        action="store_true",
        dest="continue_session",
        help="Continue from the most recent saved session",
    )
    continuation_group.add_argument(
        "--resume",
        nargs="?",
        const=True,
        default=None,
        metavar="SESSION_ID",
        help="Resume a session. Without SESSION_ID, shows an interactive picker.",
    )
    return parser.parse_args()


def check_and_resolve_trusted_folder(cwd: Path) -> None:
    if cwd.resolve() == Path.home().resolve():
        return

    detected_files = find_trustable_files(cwd)

    if not detected_files:
        return

    is_folder_trusted = trusted_folders_manager.is_trusted(cwd)

    if is_folder_trusted is not None:
        return

    try:
        is_folder_trusted = ask_trust_folder(cwd, detected_files)
    except (KeyboardInterrupt, EOFError, TrustDialogQuitException):
        sys.exit(0)
    except Exception as e:
        rprint(f"[yellow]Error showing trust dialog: {e}[/]")
        return

    if is_folder_trusted is True:
        trusted_folders_manager.add_trusted(cwd)
    elif is_folder_trusted is False:
        trusted_folders_manager.add_untrusted(cwd)


_PERMISSION_MODE_TO_AGENT: dict[str, str] = {
    "default": "default",
    "plan": "plan",
    "acceptEdits": "accept-edits",
    "bypassPermissions": "auto-approve",
    "auto": "auto-approve",
}


def _resolve_claude_code_flag_aliases(args: argparse.Namespace) -> None:
    """Normalize Claude Code-style CLI flags onto Vibe's internal fields.

    Precedence (highest wins): explicit ``--agent`` > ``--dangerously-skip-permissions``
    > ``--permission-mode``. ``--model`` becomes ``VIBE_ACTIVE_MODEL`` so it
    flows through the pydantic settings layer. ``--add-dir`` trusts each
    listed directory for this session.
    """
    if args.dangerously_skip_permissions:
        if args.agent and args.agent != "auto-approve":
            rprint(
                f"[yellow]--dangerously-skip-permissions overrides "
                f"--agent {args.agent} → auto-approve[/]"
            )
        args.agent = "auto-approve"

    if args.permission_mode and not args.agent:
        args.agent = _PERMISSION_MODE_TO_AGENT[args.permission_mode]

    if args.model:
        os.environ["VIBE_ACTIVE_MODEL"] = args.model

    if args.system_prompt:
        os.environ["VIBE_SYSTEM_PROMPT"] = args.system_prompt
    if args.append_system_prompt:
        os.environ["VIBE_APPEND_SYSTEM_PROMPT"] = args.append_system_prompt

    if args.disallowed_tools:
        # pydantic-settings parses VIBE_DISABLED_TOOLS as a JSON array, not
        # a CSV. Use the JSON form so passing a single tool still works.
        import json

        os.environ.setdefault(
            "VIBE_DISABLED_TOOLS", json.dumps(args.disallowed_tools)
        )

    # Map streaming aliases to vibe's existing name.
    if getattr(args, "output", None) == "stream-json":
        args.output = "streaming"


def main() -> None:
    args = parse_arguments()
    _resolve_claude_code_flag_aliases(args)

    if args.workdir:
        workdir = args.workdir.expanduser().resolve()
        if not workdir.is_dir():
            rprint(
                f"[red]Error: --workdir does not exist or is not a directory: {workdir}[/]"
            )
            sys.exit(1)
        os.chdir(workdir)

    try:
        cwd = Path.cwd()
    except FileNotFoundError:
        rprint(
            "[red]Error: Current working directory no longer exists.[/]\n"
            "[yellow]The directory you started vibe from has been deleted. "
            "Please change to an existing directory and try again, "
            "or use --workdir to specify a working directory.[/]"
        )
        sys.exit(1)

    if args.trust or args.dangerously_skip_permissions:
        # --dangerously-skip-permissions implies trust: the user has already
        # accepted that this session bypasses safety gates.
        trusted_folders_manager.trust_for_session(cwd)

    for extra_dir in args.add_dir:
        d = Path(extra_dir).expanduser().resolve()
        if not d.is_dir():
            rprint(f"[yellow]--add-dir: skipping non-directory {d}[/]")
            continue
        trusted_folders_manager.trust_for_session(d)

    is_interactive = args.prompt is None
    if is_interactive:
        check_and_resolve_trusted_folder(cwd)
    init_harness_files_manager("user", "project")

    from vibe.cli.cli import run_cli

    run_cli(args)


if __name__ == "__main__":
    main()
