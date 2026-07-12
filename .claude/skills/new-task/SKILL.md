---
name: new-task
description: >
  Author a new feature/fix folder of tasks under ai-flow/docs/tasks/ from a requirement or a spec.
  Use when the user wants to create, write up, or decompose a task/feature/fix into executable tasks.
---

# new-task

Route task authoring to the `task-author` subagent.

1. Read `ai-flow/docs/prompts/PROMT_TASKS.md` for the decomposition rules, folder layout, and formats.
2. Delegate to the **task-author** subagent (via the Agent/Task tool), passing the user's requirement
   or the referenced spec (`ai-flow/docs/specs/...`).
3. Report the created feature folder `ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/` — its DesignReview
   `README.md` and the task files inside.

This skill is thin — all logic lives in the `task-author` subagent. Do not author tasks inline here.
