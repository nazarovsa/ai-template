#!/usr/bin/env python3
"""
ai-flow installer / adapter.

Deploys the flow into a new or existing repository, adapts the Claude-Code-specific pieces
(subagents / skills) to another tool, and configures the Serena MCP server for that tool.

Layout: everything except the root-anchored files lives under `ai-flow/`. The root keeps only
CLAUDE.md, AGENTS.md, .claude/ and .serena/ (tools auto-discover these there).

Usage:
    python ai-flow/init.py init [--target DIR] [--tool TOOL] [--lang LANG] [--comm-lang LANG] [--force] [--no-serena]
    python ai-flow/init.py adapt --tool TOOL [--target DIR]
    python ai-flow/init.py setup-mcp --tool TOOL [--target DIR]   (alias: setup-serena)
    python ai-flow/init.py list-tools
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

SUPPORTED_TOOLS = ["claude", "codex", "cursor", "gemini", "zcode"]
RUNNABLE_AGENTS = {"claude", "codex", "zcode"}  # can be default_agent in agents.yml
SUBAGENTS = ["prd-author", "task-author", "doc-keeper"]
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
    "ai-flow/docs/prompts/PROMT_SERENA.md",
    "ai-flow/docs/prompts/PROMT_CI.md",
    "ai-flow/docs/specs/README.md",
    "ai-flow/docs/tasks/README.md",
    "ai-flow/docs/CHANGELOG.md",
    "ai-flow/hooks/check_memory_sync.py",
    "ai-flow/hooks/hooks.config.json",
    ".claude/agents/prd-author.md",
    ".claude/agents/task-author.md",
    ".claude/agents/doc-keeper.md",
    ".claude/skills/new-prd/SKILL.md",
    ".claude/skills/new-task/SKILL.md",
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


def apply_tool_default(target: Path, tool: str) -> None:
    if tool in RUNNABLE_AGENTS:
        _replace_line(target / "ai-flow" / "agents.yml",
                      "default_agent:", f"default_agent: {tool}")
        info(f"default_agent: {tool}")


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


def merge_settings(target: Path, tool: str) -> None:
    """Merge the SessionStart memory-sync hook AND the enabledMcpjsonServers trust list into
    <target>/.claude/settings.json. Without the latter the .mcp.json servers never start under
    `--dangerously-skip-permissions`."""
    if tool not in ("claude", "zcode"):
        return
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
# tool adapters (subagents/skills -> native mechanism)
# ---------------------------------------------------------------------------

def _agent_body(target: Path, name: str) -> tuple[str, str]:
    """Return (description, body-without-frontmatter) for a subagent."""
    path = target / ".claude" / "agents" / f"{name}.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    desc, body = name, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            fm, body = parts[1], parts[2].lstrip()
            for ln in fm.splitlines():
                if ln.strip().startswith("description:"):
                    desc = ln.split(":", 1)[1].strip().strip(">").strip() or name
    return desc, body


def _redirect_text() -> str:
    return ("This project is configured through **CLAUDE.md** (single source of truth).\n"
            "Read and follow ./CLAUDE.md for rules, the task workflow (ai-flow/docs/), and the\n"
            "Serena memory knowledge base. Do not duplicate rules here.\n")


def generate_adapters(target: Path, tool: str) -> None:
    if tool in ("claude", "zcode"):
        info("native .claude/agents + .claude/skills reused (no adapter needed)")
        return

    if tool == "codex":
        (target / "AGENTS.md").exists() or (target / "AGENTS.md").write_text(
            "# AGENTS.md\n\n" + _redirect_text(), encoding="utf-8")
        d = target / ".codex" / "prompts"
        d.mkdir(parents=True, exist_ok=True)
        for name in SUBAGENTS:
            _, body = _agent_body(target, name)
            (d / f"{name}.md").write_text(body, encoding="utf-8")
        info(f"wrote .codex/prompts/*.md ({', '.join(SUBAGENTS)}) + AGENTS.md")

    elif tool == "cursor":
        d = target / ".cursor" / "rules"
        d.mkdir(parents=True, exist_ok=True)
        (d / "000-claude.mdc").write_text(
            "---\ndescription: Project rules\nalwaysApply: true\n---\n\n" + _redirect_text(),
            encoding="utf-8")
        for name in SUBAGENTS:
            desc, body = _agent_body(target, name)
            (d / f"{name}.mdc").write_text(
                f"---\ndescription: {desc}\nalwaysApply: false\n---\n\n{body}",
                encoding="utf-8")
        info("wrote .cursor/rules/*.mdc")

    elif tool == "gemini":
        (target / "GEMINI.md").write_text("# GEMINI.md\n\n" + _redirect_text(), encoding="utf-8")
        d = target / ".gemini" / "prompts"
        d.mkdir(parents=True, exist_ok=True)
        for name in SUBAGENTS:
            _, body = _agent_body(target, name)
            (d / f"{name}.md").write_text(body, encoding="utf-8")
        info("wrote GEMINI.md + .gemini/prompts/*.md")


# ---------------------------------------------------------------------------
# MCP setup (Serena + codebase-memory-mcp code graph)
# ---------------------------------------------------------------------------

def _uvx_args(context: str, target: Path) -> list[str]:
    return ["--from", SERENA_REPO, "serena", "start-mcp-server",
            "--context", context, "--project", str(target)]


def setup_mcp(target: Path, tool: str) -> None:
    if shutil.which("uvx") is None:
        info("uvx not found — install `uv` (https://astral.sh/uv), then re-run setup-mcp.")

    if tool in ("claude", "zcode"):
        # The committed project-level .mcp.json is the single source of truth (local + CI): it
        # declares both Serena and codebase-memory-mcp. Do NOT `claude mcp add serena` — that
        # registers a second copy at user scope and double-registers the server. Just verify the
        # file and the runtime dependencies, then remind about the trust list.
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

    elif tool == "codex":
        cfg = Path.home() / ".codex" / "config.toml"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
        if "[mcp_servers.serena]" in text:
            info("Serena already present in ~/.codex/config.toml")
        else:
            args = _uvx_args("codex", target)
            arg_list = ", ".join(json.dumps(a) for a in args)
            block = f'\n[mcp_servers.serena]\ncommand = "uvx"\nargs = [{arg_list}]\n'
            cfg.write_text(text + block, encoding="utf-8")
            info(f"added Serena MCP to {cfg}")

    elif tool == "cursor":
        mcp = target / ".cursor" / "mcp.json"
        mcp.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if mcp.exists():
            try:
                data = json.loads(mcp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
        data.setdefault("mcpServers", {})["serena"] = {
            "command": "uvx", "args": _uvx_args("ide-assistant", target)}
        mcp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        info(f"wrote {mcp}")

    else:
        args = _uvx_args("ide-assistant", target)
        info(f"add this MCP server to your tool manually:  uvx {' '.join(args)}")

    info("Next: run ai-flow/docs/prompts/PROMT_SERENA.md (or the /sync-docs skill) to populate memory.")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_init(args) -> None:
    tool = args.tool
    if tool not in SUPPORTED_TOOLS:
        print(f"ERROR: unknown tool '{tool}'. Supported: {', '.join(SUPPORTED_TOOLS)}")
        sys.exit(1)
    target = Path(args.target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    print(f"Deploying ai-flow into: {target}  (tool={tool})")

    copied, skipped = copy_manifest(target, force=args.force)
    info(f"files: {copied} copied, {skipped} skipped")
    apply_lang(target, args.lang)
    apply_comm_lang(target, args.comm_lang)
    apply_tool_default(target, tool)
    merge_gitignore(target)
    generate_adapters(target, tool)
    merge_settings(target, tool)
    if not args.no_serena:
        setup_mcp(target, tool)

    print("\nDone. Next steps:")
    print("  1) Verify .serena/project.yml language and ai-flow/agents.yml agent flags.")
    print("  2) Populate memory: run ai-flow/docs/prompts/PROMT_SERENA.md (or /sync-docs).")
    print("  3) Author tasks (/new-task) and run:  python ai-flow/run_tasks.py")


def cmd_adapt(args) -> None:
    if args.tool not in SUPPORTED_TOOLS:
        print(f"ERROR: unknown tool '{args.tool}'. Supported: {', '.join(SUPPORTED_TOOLS)}")
        sys.exit(1)
    target = Path(args.target).resolve()
    print(f"Adapting for tool={args.tool} in {target}")
    apply_tool_default(target, args.tool)
    generate_adapters(target, args.tool)


def cmd_setup_mcp(args) -> None:
    if args.tool not in SUPPORTED_TOOLS:
        print(f"ERROR: unknown tool '{args.tool}'. Supported: {', '.join(SUPPORTED_TOOLS)}")
        sys.exit(1)
    setup_mcp(Path(args.target).resolve(), args.tool)


def cmd_list_tools(_args) -> None:
    print("Supported tools:")
    for t in SUPPORTED_TOOLS:
        native = " (native subagents/skills)" if t in ("claude", "zcode") else ""
        runnable = " [run_tasks agent]" if t in RUNNABLE_AGENTS else ""
        print(f"  - {t}{native}{runnable}")


def main() -> None:
    p = argparse.ArgumentParser(description="ai-flow installer / adapter.")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("init", help="deploy the flow into a new or existing repo")
    pi.add_argument("--target", default=".")
    pi.add_argument("--tool", default="claude")
    pi.add_argument("--lang", default="python")
    pi.add_argument("--comm-lang", default="en")
    pi.add_argument("--force", action="store_true")
    pi.add_argument("--no-serena", action="store_true")
    pi.set_defaults(func=cmd_init)

    pa = sub.add_parser("adapt", help="(re)generate tool adapters")
    pa.add_argument("--tool", required=True)
    pa.add_argument("--target", default=".")
    pa.set_defaults(func=cmd_adapt)

    ps = sub.add_parser("setup-mcp", aliases=["setup-serena"],
                        help="configure the MCP servers (Serena + code graph) for a tool")
    ps.add_argument("--tool", required=True)
    ps.add_argument("--target", default=".")
    ps.set_defaults(func=cmd_setup_mcp)

    pl = sub.add_parser("list-tools", help="list supported tools")
    pl.set_defaults(func=cmd_list_tools)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
