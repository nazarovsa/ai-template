#!/usr/bin/env python3
"""
ai-flow installer.

Deploys the flow into a new or existing repository and configures the MCP servers
(Serena + codebase-memory-mcp code graph) for Claude Code.

Claude Code is the only tool this installer configures. To run the flow under a different
agentic CLI (Codex, Cursor, Gemini, zcode, …), install it here first and then hand that tool
`ai-flow/docs/prompts/PROMT_TOOL.md` — it adapts the subagents, skills, hooks, MCP wiring and
the orchestrator command to that tool's own mechanisms.

Layout: everything except the root-anchored files lives under `ai-flow/`. The root keeps only
CLAUDE.md, AGENTS.md, .claude/ and .serena/ (tools auto-discover these there).

Usage:
    python ai-flow/init.py init [--target DIR] [--lang LANG] [--comm-lang LANG] [--force] [--no-serena]
    python ai-flow/init.py setup-mcp [--target DIR]   (alias: setup-serena)
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

FLOW_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = FLOW_DIR.parent

SERENA_REPO = "git+https://github.com/oraios/serena"
HOOK_COMMAND = "python ai-flow/hooks/check_memory_sync.py"
# MCP servers declared in the committed .mcp.json — Claude Code must trust them non-interactively
# (under --dangerously-skip-permissions) via .claude/settings.json's enabledMcpjsonServers.
MCPJSON_SERVERS = ["serena", "codebase-memory-mcp"]
GRAPH_BIN = "codebase-memory-mcp"

# Template files copied on `init` (relative to the repo root).
MANIFEST = [
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    ".gitignore",
    ".mcp.json",
    "ai-flow/run_tasks.py",
    "ai-flow/init.py",
    "ai-flow/agents.yml",
    "ai-flow/docs/prompts/PROMT_PRD.md",
    "ai-flow/docs/prompts/PROMT_SPEC.md",
    "ai-flow/docs/prompts/PROMT_TASKS.md",
    "ai-flow/docs/prompts/PROMT_AGENT.md",
    "ai-flow/docs/prompts/PROMT_VERIFY.md",
    "ai-flow/docs/prompts/PROMT_SERENA.md",
    "ai-flow/docs/prompts/PROMT_CI.md",
    "ai-flow/docs/prompts/PROMT_TOOL.md",
    "ai-flow/docs/specs/README.md",
    "ai-flow/docs/tasks/README.md",
    "ai-flow/docs/CHANGELOG.md",
    "ai-flow/hooks/check_memory_sync.py",
    "ai-flow/hooks/hooks.config.json",
    ".claude/agents/prd-author.md",
    ".claude/agents/task-author.md",
    ".claude/agents/doc-keeper.md",
    ".claude/agents/task-runner.md",
    ".claude/skills/new-prd/SKILL.md",
    ".claude/skills/new-task/SKILL.md",
    ".claude/skills/run-tasks/SKILL.md",
    ".claude/skills/sync-docs/SKILL.md",
    ".serena/project.yml",
    ".serena/memories/suggested-commands.md",
    ".serena/memories/task-completion.md",
    ".github/workflows/ai-flow-tasks.yml",
]

COMM_LANG = {
    "en": "English", "ru": "Russian", "de": "German", "fr": "French",
    "es": "Spanish", "pt": "Portuguese", "uk": "Ukrainian", "zh": "Chinese",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def info(msg: str) -> None:
    print(f"  {msg}")


def copy_manifest(target: Path, *, force: bool) -> tuple[int, int]:
    copied = skipped = 0
    for rel in MANIFEST:
        src = SOURCE_ROOT / rel
        if not src.exists():
            continue
        dst = target / rel
        if dst.exists() and not force:
            info(f"skip (exists): {rel}")
            skipped += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied, skipped


def _replace_line(path: Path, contains: str, new_line: str) -> None:
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    out = [new_line if contains in ln else ln for ln in lines]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def apply_lang(target: Path, lang: str) -> None:
    """Set the Serena project language."""
    pyml = target / ".serena" / "project.yml"
    if not pyml.exists():
        return
    lines = pyml.read_text(encoding="utf-8").splitlines()
    out, i = [], 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].strip() == "languages:":
            out.append(f"  - {lang}")
            # skip existing list items
            i += 1
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                i += 1
            continue
        i += 1
    pyml.write_text("\n".join(out) + "\n", encoding="utf-8")
    info(f"serena language: {lang}")


def apply_comm_lang(target: Path, comm_lang: str) -> None:
    name = COMM_LANG.get(comm_lang.lower(), comm_lang.capitalize())
    _replace_line(
        target / "CLAUDE.md",
        "Communication language:",
        f"**Communication language: {name}.** <!-- set by ai-flow/init.py --comm-lang -->",
    )
    info(f"communication language: {name}")


def merge_gitignore(target: Path) -> None:
    gi = target / ".gitignore"
    marker = "# --- ai-flow ---"
    block = (
        f"\n{marker}\n.serena/cache/\n.claude/cache/\n.claude/tsc-cache/\n"
        "__pycache__/\n*.pyc\nBUILD_PROMPT.md\n"
    )
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if marker in existing:
        return
    gi.write_text(existing + block, encoding="utf-8")
    info("updated .gitignore")


def merge_settings(target: Path) -> None:
    """Merge the SessionStart memory-sync hook AND the enabledMcpjsonServers trust list into
    <target>/.claude/settings.json. Without the latter the .mcp.json servers never start under
    `--dangerously-skip-permissions`."""
    settings = target / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if settings.exists():
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            info("existing .claude/settings.json is not valid JSON — add the hook + enabledMcpjsonServers manually")
            return
    changed = False

    # Trust the committed .mcp.json servers (Serena + code graph) — union, preserving order.
    trusted = data.setdefault("enabledMcpjsonServers", [])
    for name in MCPJSON_SERVERS:
        if name not in trusted:
            trusted.append(name)
            changed = True

    # Register the SessionStart memory-sync hook (idempotent).
    session = data.setdefault("hooks", {}).setdefault("SessionStart", [])
    already = any(
        h.get("command") == HOOK_COMMAND
        for group in session if isinstance(group, dict)
        for h in group.get("hooks", []) if isinstance(h, dict)
    )
    if not already:
        session.append({"hooks": [{"type": "command", "command": HOOK_COMMAND}]})
        changed = True

    if not changed:
        info("SessionStart hook + enabledMcpjsonServers already present in .claude/settings.json")
        return
    settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    info("merged SessionStart hook + enabledMcpjsonServers into .claude/settings.json")


# ---------------------------------------------------------------------------
# MCP setup (Serena + codebase-memory-mcp code graph)
# ---------------------------------------------------------------------------

def setup_mcp(target: Path) -> None:
    # The committed project-level .mcp.json is the single source of truth (local + CI): it declares
    # both Serena and codebase-memory-mcp. Do NOT `claude mcp add serena` — that registers a second
    # copy at user scope and double-registers the server. Just verify the file and the runtime
    # dependencies, then remind about the trust list.
    if shutil.which("uvx") is None:
        info("uvx not found — install `uv` (https://astral.sh/uv), then re-run setup-mcp.")

    mcp = target / ".mcp.json"
    if mcp.exists():
        info(".mcp.json present — project-level source for serena + codebase-memory-mcp")
    else:
        info("WARNING: .mcp.json is missing — re-run `init` (or copy it from the template).")
    if shutil.which(GRAPH_BIN) is None:
        info(f"{GRAPH_BIN} not found on PATH — install it (README: 'Запуск задач в GitHub "
             "Actions') so the code graph is available.")
    info("Claude Code trusts both servers via .claude/settings.json → enabledMcpjsonServers "
         "(merged by init).")
    info("Another tool than Claude Code? It will not read .mcp.json — hand it "
         "ai-flow/docs/prompts/PROMT_TOOL.md to wire the servers its own way.")
    info("Next: run ai-flow/docs/prompts/PROMT_SERENA.md (or the /sync-docs skill) to populate memory.")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_init(args) -> None:
    target = Path(args.target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    print(f"Deploying ai-flow into: {target}  (tool: Claude Code)")

    copied, skipped = copy_manifest(target, force=args.force)
    info(f"files: {copied} copied, {skipped} skipped")
    apply_lang(target, args.lang)
    apply_comm_lang(target, args.comm_lang)
    merge_gitignore(target)
    merge_settings(target)
    if not args.no_serena:
        setup_mcp(target)

    print("\nDone. Next steps:")
    print("  1) Verify .serena/project.yml language and ai-flow/agents.yml agent flags.")
    print("  2) Populate memory: run ai-flow/docs/prompts/PROMT_SERENA.md (or /sync-docs).")
    print("  3) Author tasks (/new-task) and run:  python ai-flow/run_tasks.py")
    print("  Not using Claude Code? Open your own agentic CLI here and give it")
    print("  ai-flow/docs/prompts/PROMT_TOOL.md to adapt the flow to that tool.")


def cmd_setup_mcp(args) -> None:
    setup_mcp(Path(args.target).resolve())


def main() -> None:
    p = argparse.ArgumentParser(description="ai-flow installer (Claude Code).")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("init", help="deploy the flow into a new or existing repo")
    pi.add_argument("--target", default=".")
    pi.add_argument("--lang", default="python")
    pi.add_argument("--comm-lang", default="en")
    pi.add_argument("--force", action="store_true")
    pi.add_argument("--no-serena", action="store_true")
    pi.set_defaults(func=cmd_init)

    ps = sub.add_parser("setup-mcp", aliases=["setup-serena"],
                        help="verify the MCP servers (Serena + code graph) for Claude Code")
    ps.add_argument("--target", default=".")
    ps.set_defaults(func=cmd_setup_mcp)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
