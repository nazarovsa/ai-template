# task-completion

## When to consult
Before declaring any task done — whether run via `ai-flow/run_tasks.py` or implemented interactively.

## Definition of done
A task is complete only when ALL hold:
1. The **Changes** are implemented and all **Acceptance Criteria** in the task file are satisfied.
2. **Blocking gate — the project builds and runs.** The whole solution compiles/builds cleanly and
   its **tests pass** with the project's own tooling (see `read_memory("build-and-verify")` for the
   exact commands). No build errors, no broken run, no weakened/skipped tests. If it does not build,
   the task is NOT done: never print `<promise>COMPLETE</promise>` and never let it be committed —
   fix it or report the failing command and its output.
3. A factual entry is APPENDED to `ai-flow/docs/CHANGELOG.md` (what changed + files).
4. If a reusable pattern was introduced/changed → it is documented ONLY as memory: the matching
   `.serena/memories/<name>.md` is updated via `write_memory(...)` and the "Project knowledge" table
   in `CLAUDE.md` is in sync. Patterns are never duplicated into the changelog.
5. If behavior/architecture/commands changed → the corresponding `ai-flow/docs/` file is updated.

## Feature spec (living docs)
- Keep `ai-flow/docs/specs/<feature>/README.md` (target) and `IMPLEMENTED.md` (as-built) current;
  add the feature to the index in `ai-flow/docs/specs/README.md`.

## Under the orchestrator
- Print exactly `<promise>COMPLETE</promise>` when done. Do NOT git commit — the orchestrator commits
  (single-line message, ≤155 chars, no tool/AI mentions).
- On success the orchestrator MOVES the task file into the feature's `done/` subfolder.
