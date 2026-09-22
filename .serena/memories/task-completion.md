# task-completion

## When to consult
Before declaring any task or feature done — whether run via `ai-flow/run_tasks.py` or implemented
interactively.

## The green-tests gate follows the requested unit of work
- **A whole feature was requested** (`run_tasks.py` without `--task`, or "implement feature X" in a
  session) → the unit is the feature. Each task writes its tests test-first and must leave the solution
  compiling, but does NOT run the tests. After the feature's last task, one verification pass
  (`ai-flow/docs/prompts/PROMT_VERIFY.md`) builds, runs the WHOLE test suite, fixes failures and
  repeats until green. The feature is done only then.
- **A single task was requested** (`run_tasks.py --task`, "do the next task") → the unit is the task:
  it builds and runs the tests itself.
- `test_gate: task` in `ai-flow/agents.yml` switches every run back to per-task test runs.

## Definition of done — a task
1. The **Changes** are implemented and all **Acceptance Criteria** in the task file are satisfied;
   every **Test Cases** row exists as a real test.
2. **Blocking gate — the project builds.** The whole solution, test projects included, compiles/builds
   cleanly with the project's own tooling (see `read_memory("build-and-verify")` for the exact
   commands). Under the task gate its **tests pass** too. If it does not build, the task is NOT done:
   never print `<promise>COMPLETE</promise>` and never let it be committed — fix it or report the
   failing command and its output. Never weaken/skip/delete tests.
3. A factual entry is APPENDED to `ai-flow/docs/CHANGELOG.md` (what changed + files).
4. If a reusable pattern was introduced/changed → it is documented ONLY as memory: the matching
   `.serena/memories/<name>.md` is updated via `write_memory(...)` and the "Project knowledge" table
   in `CLAUDE.md` is in sync. Patterns are never duplicated into the changelog.
5. If behavior/architecture/commands changed → the corresponding `ai-flow/docs/` file is updated.

## Definition of done — a feature (feature gate)
All its tasks are done AND the verification pass is green: the solution builds and the whole test
suite passes, with nothing weakened. Fixes are logged in the changelog; behavior changes are reflected
in `IMPLEMENTED.md`.

## Feature spec (living docs)
- Keep `ai-flow/docs/specs/<feature>/README.md` (target) and `IMPLEMENTED.md` (as-built) current;
  add the feature to the index in `ai-flow/docs/specs/README.md`.

## Under the orchestrator
- Print exactly `<promise>COMPLETE</promise>` when done. Do NOT git commit — the orchestrator commits
  (single-line message, ≤155 chars, no tool/AI mentions).
- On success the orchestrator MOVES the task file into the feature's `done/` subfolder and commits.
- A feature with all tasks in `done/` but not archived is unverified: the orchestrator runs the
  verification pass (strict — no marker means failure), and only a green pass archives the feature
  into `ai-flow/docs/tasks/done/` with its own commit. A failed pass leaves the feature active; the
  next feature run retries it.
