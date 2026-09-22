# task-completion

## When to consult
Before declaring any task or feature done — whether run via `ai-flow/run_tasks.py` or implemented
interactively.

## Tests and docs follow the requested unit of work
- **A whole feature was requested** (`run_tasks.py` without `--task`, or "implement feature X" in a
  session) → the unit is the feature. Each task writes its tests test-first and must leave the solution
  compiling, but does NOT run the tests, and records what it built ONLY in the feature notes
  (`ai-flow/docs/tasks/<feature>/NOTES.md`). After the feature's last task, one verification pass
  (`ai-flow/docs/prompts/PROMT_VERIFY.md`) builds, runs the WHOLE test suite, fixes failures and
  repeats until green, then records the feature's docs once from the notes. The feature is done only
  then.
- **A single task was requested** (`run_tasks.py --task`, "do the next task") → the unit is the task:
  it runs the tests and updates the docs itself.
- `unit_of_work: task` in `ai-flow/agents.yml` (legacy key `test_gate`) switches every run back to
  per-task tests and docs.

## Definition of done — a task
1. The **Changes** are implemented and all **Acceptance Criteria** in the task file are satisfied;
   every **Test Cases** row exists as a real test.
2. **Blocking gate — the project builds.** The whole solution, test projects included, compiles/builds
   cleanly with the project's own tooling (see `read_memory("build-and-verify")` for the exact
   commands). Under the task unit its **tests pass** too. If it does not build, the task is NOT done:
   never print `<promise>COMPLETE</promise>` and never let it be committed — fix it or report the
   failing command and its output. Never weaken/skip/delete tests.
3. An entry is APPENDED to the feature notes `<feature>/NOTES.md`: built, files, API for later tasks,
   decisions & deviations, patterns / domain rules, conflicts, docs to update, tests.
4. Under the task unit only: a changelog entry, the feature spec + `IMPLEMENTED.md`, memories + the
   CLAUDE.md table, and any changed `ai-flow/docs/` file are updated by the task itself.

## Definition of done — a feature (feature unit)
All its tasks are done AND the verification pass is green: the solution builds, the whole test suite
passes with nothing weakened, and the docs are recorded from the notes — one changelog entry, spec
target + as-built, specs index, memories for every listed pattern / domain rule (CLAUDE.md table in
sync), every listed conflict resolved or reported.

## Context map
Every task carries a `## Context` section (PROMT_TASKS §6a): the template sections, memories, spec
section and 3–7 code anchors the executor reads first. Start there and in the feature notes; widen the
search only when they are not enough — never load a whole template by default.

## Under the orchestrator
- Print exactly `<promise>COMPLETE</promise>` when done. Do NOT git commit — the orchestrator commits
  (single-line message, ≤155 chars, no tool/AI mentions).
- On success the orchestrator MOVES the task file into the feature's `done/` subfolder and commits.
- A feature with all tasks in `done/` but not archived is unverified: the orchestrator runs the
  verification pass (strict — no marker means failure), and only a green pass archives the feature
  into `ai-flow/docs/tasks/done/` with its own commit. A failed pass leaves the feature active; the
  next feature run retries it.
- Prompt size: the orchestrator sends only the last `context.changelog_entries` changelog entries,
  and does not embed `CLAUDE.md` for an agent with `loads_claude_md: true` (the CLI loads it itself).

## Parallel batches
- Tasks of one feature that mutually list each other in `Parallel with:` (and are all ready) run as
  one atomic batch, each in an isolated git worktree. A **parallel worker** writes product code +
  tests and meets the build gate, but touches NO shared doc (`CLAUDE.md`, changelog, specs, memories,
  task Markdown incl. `NOTES.md`) — it ends its summary with its notes entry. The **integration pass**
  writes one `NOTES.md` entry per batched task, reconciles, builds (under the task unit also tests +
  docs); only then is the main branch fast-forwarded. Needs a clean worktree and git auto-commit.
- `Depends on:` stays a hard gate. Keep every reference on that line (indented continuation lines are
  fine, a new bullet is not); parentheses, backticks, `.md` and text after an em dash are ignored.
