---
name: sync-docs
description: >
  Bootstrap or refresh Serena memories and docs to match the current codebase. Use to populate project
  memories the first time, or after code/behavior changes when docs or the CLAUDE.md knowledge table
  have drifted.
---

# sync-docs

Route documentation and knowledge maintenance to the `doc-keeper` subagent.

1. Determine the scope:
   - **Full bootstrap** (no project memories yet) → run `ai-flow/docs/prompts/PROMT_SERENA.md`.
   - **Refresh** → the given scope or the recent changes.
2. Delegate to the **doc-keeper** subagent (via the Agent/Task tool).
3. Report updated `ai-flow/docs/*`, `.serena/memories/*`, and the "Project knowledge" table in `CLAUDE.md`.

This skill is thin — all logic lives in the `doc-keeper` subagent. Do not edit docs/memories inline here.
