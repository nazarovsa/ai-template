# Changelog

Chronological journal of completed tasks — each task run APPENDS an entry below.
Reusable patterns are NOT recorded here: they live in Serena memory (`.serena/memories/*`)
and are indexed in the CLAUDE.md "Project knowledge" table.

---

## 2026-08-22 — Project-level Codex MCP configuration

- Added `.codex/config.toml` to the installer manifest so initialized repositories support Codex
  alongside the existing Claude Code `.mcp.json` configuration.
- Updated `ai-flow/init.py` to configure both Serena (`--context codex`) and
  `codebase-memory-mcp` in the project-level Codex configuration.
- Updated `README.md` and `CLAUDE.md` with the dual-client MCP setup and session refresh guidance.
