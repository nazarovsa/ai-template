#!/usr/bin/env python3
"""
Hook: keep the CLAUDE.md "Project knowledge" table in sync with Serena memories.

Compares the `read_memory("...")` calls listed in CLAUDE.md against the actual `.md` files in
`.serena/memories/` and reports:
  - dangling rows  — the table references a memory that does not exist;
  - orphan memories — a memory file exists but is not referenced in the table.

Designed as a Claude Code hook (registered in .claude/settings.json). Reads the hook event JSON from
stdin (for the project `cwd`); if absent, falls back to the current working directory. Stdlib only.

Configuration: ai-flow/hooks/hooks.config.json → "memory_sync":
  enabled          true|false          master switch
  mode             "warn" | "off"      warn = print a non-blocking notice; off = do nothing
  check_dangling   true|false          report table rows without a memory file
  check_orphans    true|false          report memory files missing from the table
  ignore_memories  ["name", ...]       memory names never treated as orphans (e.g. shipped ones)

Exit code is always 0 (non-blocking). To make it blocking, register it on a gating event and change
the tail to exit(2) when issues are found.
"""

import json
import re
import sys
from pathlib import Path

# Some Windows consoles default to a non-UTF-8 code page; keep output ASCII-safe anyway.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_CONFIG = {
    "enabled": True,
    "mode": "warn",
    "check_dangling": True,
    "check_orphans": True,
    "ignore_memories": ["suggested-commands", "task-completion"],
}


def project_root() -> Path:
    """Prefer the cwd from the hook event JSON; fall back to the process cwd."""
    try:
        data = json.load(sys.stdin)
        if isinstance(data, dict) and data.get("cwd"):
            return Path(data["cwd"])
    except Exception:
        pass
    return Path.cwd()


def load_config(root: Path) -> dict:
    cfg_path = root / "ai-flow" / "hooks" / "hooks.config.json"
    cfg = dict(DEFAULT_CONFIG)
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg.update(raw.get("memory_sync", {}))
    except Exception:
        pass
    return cfg


def table_memories(claude_md: Path) -> set[str]:
    if not claude_md.exists():
        return set()
    text = claude_md.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'read_memory\(\s*["\']([^"\']+)["\']\s*\)', text))


def existing_memories(memories_dir: Path) -> set[str]:
    if not memories_dir.exists():
        return set()
    return {p.stem for p in memories_dir.glob("*.md")}


def main() -> None:
    root = project_root()
    cfg = load_config(root)
    if not cfg.get("enabled", True) or cfg.get("mode") == "off":
        return

    referenced = table_memories(root / "CLAUDE.md")
    existing = existing_memories(root / ".serena" / "memories")
    ignore = set(cfg.get("ignore_memories", []))

    problems = []
    if cfg.get("check_dangling", True):
        dangling = sorted(referenced - existing)
        if dangling:
            problems.append("CLAUDE.md references memories that do not exist: "
                            + ", ".join(dangling)
                            + " — create them (write_memory) or drop the rows.")
    if cfg.get("check_orphans", True):
        orphans = sorted(existing - referenced - ignore)
        if orphans:
            problems.append("Memories not indexed in the CLAUDE.md table: "
                            + ", ".join(orphans)
                            + " — add a read_memory row or ignore them in hooks.config.json.")

    if problems:
        print("[memory-sync] CLAUDE.md <-> .serena/memories drift:")
        for p in problems:
            print(f"  - {p}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # a hook must never break the session
        print(f"[memory-sync] skipped: {exc}")
    sys.exit(0)
