# AGENTS.md

This repository is configured through **CLAUDE.md** — the single source of truth.

Any AI tool or agent that opens this repository must read and follow
**[CLAUDE.md](./CLAUDE.md)**:

- project conventions and rules,
- the task workflow (`ai-flow/docs/tasks/`, `ai-flow/docs/prompts/`),
- the Serena memory knowledge base (load on demand).

Do not duplicate instructions here. When in doubt, defer to CLAUDE.md.

**Not Claude Code?** The subagents, skills, session hook and MCP wiring that ship with this
repository are Claude Code's own mechanisms. To get the same workflow under your tool, run
`ai-flow/docs/prompts/PROMT_TOOL.md` from this repository root — it translates those pieces into
your tool's equivalents and registers your CLI as a task executor in `ai-flow/agents.yml`.
Until then, use the prompts in `ai-flow/docs/prompts/` directly.
