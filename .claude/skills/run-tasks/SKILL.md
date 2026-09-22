---
name: run-tasks
description: >
  Run the automated task executor (ai-flow/run_tasks.py) for a feature — all of its pending tasks
  sequentially, or just the next single task. Use when the user wants to execute/run a feature's tasks,
  run the next task, or start the orchestrator.
---

# run-tasks

Route execution of the task runner to the `task-runner` subagent.

1. Determine the scope from the user's request: a specific **feature** (folder under
   `ai-flow/docs/tasks/`), and whether they want **all tasks sequentially** or just the **next task**.
   If the feature is unclear, `ls ai-flow/docs/tasks/` and confirm.
2. Delegate to the **task-runner** subagent (via the Agent/Task tool), passing the feature and the mode
   (whole feature vs. next task) plus any `--agent` / `--model` / `--max-parallel` override the user
   requested.
3. Report which tasks ran, what moved to `done/`, the feature verification pass outcome (the whole
   test suite and the feature's docs happen once per feature, after its last task), whether the feature
   was archived into `tasks/done/`, commits made, and anything that failed or is blocked.

This skill is thin — all logic lives in the `task-runner` subagent. Do not invoke `run_tasks.py` inline
here.
