# suggested-commands

## When to consult
Whenever you need to run the flow: execute tasks, initialize/adapt the template, or set up Serena.

## Commands

### Run tasks (orchestrator)
- `python ai-flow/run_tasks.py` — run all ready tasks with the default agent (`ai-flow/agents.yml`).
- `python ai-flow/run_tasks.py --agent codex --model gpt-5-codex` — pick an agent / model.
- `python ai-flow/run_tasks.py --agent zcode --model glm-4.6`
- `python ai-flow/run_tasks.py --feature user-login` — only matching feature folders.
- `python ai-flow/run_tasks.py --task add-login` — only tasks whose name matches.
- `python ai-flow/run_tasks.py --dry-run` — show the plan without executing.
- Requires: `pip install pyyaml`.

### Initialize / adapt (installer)
- `python ai-flow/init.py init --tool claude --lang python --comm-lang en` — deploy the flow here.
- `python ai-flow/init.py init --target <DIR> --tool codex` — deploy into another repo.
- `python ai-flow/init.py adapt --tool cursor` — (re)generate tool adapters.
- `python ai-flow/init.py setup-serena --tool claude` — configure the Serena MCP server for a tool.
- `python ai-flow/init.py list-tools` — supported tools.

### Hooks
- `python ai-flow/hooks/check_memory_sync.py` — check CLAUDE.md table vs `.serena/memories` (runs as a
  SessionStart hook via `.claude/settings.json`). Configure/disable in `ai-flow/hooks/hooks.config.json`.

## Where things live
- Planning prompts: `ai-flow/docs/prompts/` (PROMT_SPEC, PROMT_TASKS, PROMT_AGENT, PROMT_SERENA).
- Tasks by feature: `ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/` (task files + `done/`; `README.md` = DesignReview).
- Specs & functionality: `ai-flow/docs/specs/` (root README overview + `<feature>/README.md` target + `IMPLEMENTED.md` as-built).
- Changelog: `ai-flow/docs/CHANGELOG.md`.
- Knowledge base: `.serena/memories/`. Rules: root `CLAUDE.md`.
