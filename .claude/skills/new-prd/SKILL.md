---
name: new-prd
description: >
  Interview the user and write a PRD (Product Requirements Document) for a NEW project at
  ai-flow/docs/specs/PRD.md. Use at project kickoff / greenfield to capture vision, users, user
  scenarios, functional scope, constraints, and architecture direction before specs or tasks exist.
---

# new-prd

Kick off product discovery and produce the project's PRD.

1. Read `ai-flow/docs/prompts/PROMT_PRD.md` for the interview themes, the PRD structure, and the rules.
2. **Run the discovery interview in this conversation** — ask the user the questions **section by
   section** and wait for answers. Discovery is interactive, so the interview stays in the main chat:
   a spawned subagent cannot ask the user questions. Follow the `prd-author` role in
   `.claude/agents/prd-author.md`.
3. When every theme is covered or explicitly deferred, summarize your understanding, confirm, then
   write `ai-flow/docs/specs/PRD.md`. You may hand the collected answers to the **prd-author** subagent
   for the final write-up, or draft the file inline.
4. Report the PRD path plus the open questions / assumptions still to resolve, and point to the next
   step: `PROMT_SPEC.md` (detailed specs) or `/new-task` to decompose the first feature.

Unlike `/new-task` and `/sync-docs`, this skill is not a pure router — the interview must run in the
main conversation. Outside Claude Code, feed `ai-flow/docs/prompts/PROMT_PRD.md` to the agent directly
in its own interactive session — same result.
