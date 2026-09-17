# suggested-commands

## When to consult
Whenever you need to run the flow: execute tasks, initialize/adapt the template, or set up Serena.

## Commands

### Run tasks (orchestrator)
- `python ai-flow/run_tasks.py` — run all ready tasks with the default agent (`ai-flow/agents.yml`).
- `python ai-flow/run_tasks.py --model opus` — override the model; `--agent <name>` picks another
  entry from `agents.yml` (the template ships `claude` only).
- `python ai-flow/run_tasks.py --feature user-login` — only matching feature folders.
- `python ai-flow/run_tasks.py --task add-login` — only tasks whose name matches.
- `python ai-flow/run_tasks.py --dry-run` — show the plan without executing.
- Requires: `pip install pyyaml`.

### Initialize (installer — Claude Code)
- `python ai-flow/init.py init --lang python --comm-lang en` — deploy the flow here.
- `python ai-flow/init.py init --target <DIR>` — deploy into another repo.
- `python ai-flow/init.py setup-mcp` — verify MCP (Serena + code graph) (alias: setup-serena).

### Another agentic CLI (not Claude Code)
- Run `ai-flow/docs/prompts/PROMT_TOOL.md` from inside that CLI: it adapts the roles, entry points,
  hook, MCP wiring and the `agents.yml` executor entry to that tool. The installer does not do this.

### Hooks
- `python ai-flow/hooks/check_memory_sync.py` — check CLAUDE.md table vs `.serena/memories` (runs as a
  SessionStart hook via `.claude/settings.json`). Configure/disable in `ai-flow/hooks/hooks.config.json`.

## Where things live
- Planning prompts: `ai-flow/docs/prompts/` (PROMT_PRD, PROMT_SPEC, PROMT_TASKS, PROMT_AGENT,
  PROMT_SERENA, PROMT_CI, PROMT_TOOL).
- Tasks by feature: `ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/` (task files + `done/`; `README.md` = DesignReview).
- Specs & functionality: `ai-flow/docs/specs/` (root README overview + `<feature>/README.md` target + `IMPLEMENTED.md` as-built).
- Changelog: `ai-flow/docs/CHANGELOG.md`.
- Knowledge base: `.serena/memories/`. Rules: root `CLAUDE.md`.
