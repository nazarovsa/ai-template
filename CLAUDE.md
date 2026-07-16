# CLAUDE.md

Base repository for AI-driven projects. This is the single source of truth for rules.
Load Serena memories and docs **on demand** — do not preload everything into context.

**Communication language: English.** <!-- set by ai-flow/init.py --comm-lang -->

## Workflow

- Flow infrastructure lives under `ai-flow/`. The repo root keeps only `CLAUDE.md`, `AGENTS.md`,
  `.claude/`, `.serena/`, `.github/`.
- Planning prompts live in `ai-flow/docs/prompts/` (`PROMT_PRD`, `PROMT_SPEC`, `PROMT_TASKS`, `PROMT_AGENT`, `PROMT_SERENA`, `PROMT_CI`).
  A from-scratch project starts with `PROMT_PRD` (`/new-prd`) — an interview that produces the project
  PRD at `ai-flow/docs/specs/PRD.md`, which then feeds `PROMT_SPEC`.
- Specs & functionality live in `ai-flow/docs/specs/`: root `README.md` (project overview, filled at
  onboarding) + per-feature `<feature>/README.md` (target) + `IMPLEMENTED.md` (as-built), updated
  automatically. No separate `functionality/` folder — specs is the single home.
- **Task artifacts ALWAYS go into `ai-flow/docs/tasks/`**, grouped by feature/fix:
  `ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/` with a `README.md` (DesignReview), task files
  `<YYYYMMddHHmm_TASK>.md`, and a `done/` subfolder (see `ai-flow/docs/tasks/README.md`).
- Automated execution: `python ai-flow/run_tasks.py` (config `ai-flow/agents.yml`). On success a task
  file is MOVED into its feature's `done/` subfolder.
- In CI: `.github/workflows/ai-flow-tasks.yml` ("ai-flow · run tasks") runs the same orchestrator from
  the repo root on manual dispatch and opens a PR. It authenticates with the `CLAUDE_CODE_OAUTH_TOKEN`
  secret. Agent commands in `agents.yml` must NOT use `--bare`: bare mode skips CLAUDE.md / `.claude/`
  auto-discovery and ignores that token. To port the pipeline to another CI (GitLab, …), run
  `ai-flow/docs/prompts/PROMT_CI.md` — it carries the invariants that must survive the port.
- Completed work is journaled in `ai-flow/docs/CHANGELOG.md`. Reusable patterns go to Serena memory
  (see below), never the changelog — memory is the single knowledge store.

## Project knowledge (Serena memories)

Run `list_memories` at session start to confirm what's available. Memories are plain `.md`
files under `.serena/memories/` — readable directly even without the Serena MCP.

Always available (ship with the flow): `read_memory("suggested-commands")`, `read_memory("task-completion")`.

**Trigger table — populated by PROMT_SERENA.** A fresh template has no project-specific memories yet.
Run `ai-flow/docs/prompts/PROMT_SERENA.md` (or the `/sync-docs` skill) to discover patterns and fill
the table below with one row per created memory (never a row without a memory).

| Task trigger | Required call |
|---|---|
| _(none yet — run PROMT_SERENA)_ | |

## Always-apply rules

- Task setup → artifacts only in `ai-flow/docs/tasks/` (format: `ai-flow/docs/tasks/README.md`).
- **New/changed reusable pattern in code** → create/update the matching `.serena/memories/<name>.md`
  via `write_memory(...)` and keep the table above in sync. Never silently diverge from a memory —
  fix the memory or escalate the conflict.
- **Behavior/architecture changed** → update the corresponding file under `ai-flow/docs/` (spec / README)
  in the same change — docs must not lag behind code.
- Git commits: a single-line message, **≤155 characters**. Do NOT mention Claude, AI, or any tool —
  no `Co-Authored-By`, no "Generated with …" footers, no tool names anywhere in the message.
