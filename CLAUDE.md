# CLAUDE.md

Base repository for AI-driven projects. This is the single source of truth for rules.
Load Serena memories and docs **on demand** — do not preload everything into context.

**Communication language: English.** <!-- set by ai-flow/init.py --comm-lang -->

## Workflow

- Flow infrastructure lives under `ai-flow/`. The repo root keeps only `CLAUDE.md`, `AGENTS.md`,
  `.claude/`, `.serena/`, `.github/`.
- **Claude Code is the only tool wired out of the box** (subagents, skills, hook, `.mcp.json`).
  To work under a different agentic CLI, open that CLI here and run
  `ai-flow/docs/prompts/PROMT_TOOL.md` — it adapts the roles, entry points, hook, MCP wiring and the
  `agents.yml` executor entry to that tool. Do not hand-maintain per-tool adapters in this repo.
- Planning prompts live in `ai-flow/docs/prompts/` (`PROMT_PRD`, `PROMT_SPEC`, `PROMT_TASKS`, `PROMT_AGENT`, `PROMT_SERENA`, `PROMT_CI`, `PROMT_TOOL`).
  A from-scratch project starts with `PROMT_PRD` (`/new-prd`) — an interview that produces the project
  PRD at `ai-flow/docs/specs/PRD.md`, which then feeds `PROMT_SPEC`.
- Specs & functionality live in `ai-flow/docs/specs/`: root `README.md` (project overview, filled at
  onboarding) + per-feature `<feature>/README.md` (target) + `IMPLEMENTED.md` (as-built), updated
  automatically. No separate `functionality/` folder — specs is the single home.
- **Task artifacts ALWAYS go into `ai-flow/docs/tasks/`**, grouped by feature/fix:
  `ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/` with a `README.md` (DesignReview), task files
  `<YYYYMMddHHmm_TASK>.md`, and a `done/` subfolder (see `ai-flow/docs/tasks/README.md`).
- **A PRD is cut into key implementation milestones before it is cut into tasks.** The milestones
  live in `ai-flow/docs/tasks/MILESTONES.md` (goal, covered requirements/specs, member features,
  exit criteria, status). The last task of a milestone's last feature is always a checkpoint task:
  verify PRD **and** specs against the actual implementation, fix whatever drifted, record as-built,
  update `MILESTONES.md`, and only then cut the next milestone's tasks — never from a stale spec.
  Rules: `ai-flow/docs/prompts/PROMT_TASKS.md` §11.
- Automated execution: `python ai-flow/run_tasks.py` (config `ai-flow/agents.yml`). On success a task
  file is MOVED into its feature's `done/` subfolder; once ALL tasks of a feature are done, the whole
  feature folder is MOVED into the global archive `ai-flow/docs/tasks/done/<feature>/`.
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

When PROMT_SERENA / `/sync-docs` runs, seed a `domain-rules` memory for the domain's business
rules (formulas, coefficients, thresholds, invariants, economy) — distinct from `domain-modeling`
(how domain code is written) — and add its row here. Until then `list_memories` won't show it;
capture rules into it as domain logic is implemented (see the write path below).

## Implementation rules (core templates)

`ai-flow/docs/core_templates/` is **normative**, not reference material. Any code written in this
repository follows it:

| Template | Scope | Read it before |
|---|---|---|
| `core_templates/backend_template.md` | .NET 10 backend: solution layout, layering, domain, EF Core, services, HTTP API, JWT auth with roles, errors, options, DI, tests, build | touching any `.cs` file, `.csproj`, migration, or backend structure |
| `core_templates/frontend_template.md` | Next.js App Router frontend: directory tree, layer/import rules, data access, state, i18n, styling, config | touching any `.ts`/`.tsx` file or frontend structure |

- **Load the relevant template on demand** — before writing or reviewing code of that kind, not at
  session start. They are long; read the sections you need.
- The templates win over habit and over patterns found in unrelated code. When project reality and a
  template disagree, that is a defect: fix the code, or change the template deliberately and say so —
  never silently diverge.
- Each template ends with a **feature checklist** and an **antipatterns** list. Walk the checklist
  before declaring a feature done; the antipatterns are review-blocking.
- Fixed by the templates, not open for per-task reinvention: **.NET 10**, **JWT Bearer with roles**
  as the only auth mechanism (static API keys are forbidden), Central Package Management, migrations
  only in the migrator project, xUnit + NSubstitute.
- A project on a different stack drops or replaces the template that does not apply — but states the
  replacement in this section rather than leaving the rule dangling.
- Changing a template is a documentation change like any other: update it in the same commit as the
  code that motivated it, and reflect any reusable pattern into the matching Serena memory.

## Code graph (codebase-memory-mcp)

The committed `.mcp.json` wires two MCP servers and `.claude/settings.json` trusts both via
`enabledMcpjsonServers`: **serena** (symbol search, memories) and **codebase-memory-mcp** — a code
graph for symbol/call/usage/architecture queries (`search_code`, `query_graph`, `trace_path`,
`get_architecture`). Other agentic CLIs do not read `.mcp.json` — wiring them is part of
`ai-flow/docs/prompts/PROMT_TOOL.md`, not of this repo. Use the graph to navigate
unfamiliar code; it complements Serena, it does not replace memories as the knowledge store. Index a
repo with `index_repository` (project name = repo folder name). It degrades gracefully: if a server
is down, fall back to Serena + reading files.

In CI, `.github/workflows/ai-flow-tasks.yml` provisions this itself — it installs `uv` and the
`codebase-memory-mcp` binary, checks `claude mcp list` (non-fatal), and warms the graph with a fast
`index_repository` before the tasks run — so no manual setup is needed for the automated pipeline.

## Always-apply rules

- **A task is done only if the solution builds and runs.** Before declaring completion — before
  printing the completion marker or letting a commit happen — build the whole project and run its
  tests with the project's own tooling (`read_memory("build-and-verify")`). A red build or a broken
  run is an unfinished task: fix it or report failure. NEVER emit `<promise>COMPLETE</promise>` or
  commit a solution that does not compile/build and pass its tests.
- **Code follows `ai-flow/docs/core_templates/`** — backend and frontend templates are binding.
  Read the relevant one before writing code; walk its feature checklist before declaring done.
- Task setup → artifacts only in `ai-flow/docs/tasks/` (format: `ai-flow/docs/tasks/README.md`).
- **New/changed reusable pattern in code — or a key domain business rule** (formula, coefficient,
  threshold, mechanic/economy invariant) → create/update the matching `.serena/memories/<name>.md`
  (business rules → `domain-rules`) via `write_memory(...)` and keep the table above in sync. A changed
  rule and its enforcing code move together. Never silently diverge from a memory — fix the memory or
  escalate the conflict.
- **Behavior/architecture changed** → update the corresponding file under `ai-flow/docs/` (spec / README)
  in the same change — docs must not lag behind code.
- Git commits: a single-line message, **≤155 characters**. Do NOT mention Claude, AI, or any tool —
  no `Co-Authored-By`, no "Generated with …" footers, no tool names anywhere in the message.
