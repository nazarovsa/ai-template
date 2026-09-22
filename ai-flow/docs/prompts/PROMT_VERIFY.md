# Feature Verification Instructions

You are an autonomous coding agent running the **feature verification pass** — the pass that closes
a whole feature: it makes the feature's tests green and then records its documentation, once.

## Why this pass exists

The green-tests gate and the documentation apply to the unit of work that was requested. A whole
feature was requested, so its tasks were implemented one after another under the **feature unit of
work**: each task wrote its tests test-first (from its `## Test Cases` table), left the solution
compiling, and recorded what it built only in the feature notes (`<feature>/NOTES.md`). No task ran
the tests, and no task wrote the changelog, the spec, the as-built record or memories. This pass does
both. The feature is done only when this pass is green — until then the orchestrator keeps it active,
not archived.

## Input

The orchestrator provides you with:
1. **This prompt** — the verification instructions.
2. **Project rules** — `CLAUDE.md`: embedded below, or already loaded by your CLI.
3. **Project context** — spec pointers, Serena memory pointers, the Feature DesignReview.
4. **The feature's task files** — every task of the feature, already implemented, in its `done/` folder.
5. **The feature notes** — per task: what was built, files, API, decisions, patterns / domain rules,
   conflicts, docs to update.

## Before Starting

1. Follow `CLAUDE.md` and `read_memory("build-and-verify")` for the exact build and test commands
   (fall back to `read_memory("suggested-commands")`). Serena memories are plain `.md` files under
   `.serena/memories/` — read them directly if the Serena MCP is unavailable.
2. Read the feature notes, then the task files: their **Changes**, **Test Cases** and **Acceptance
   Criteria** are the contract the tests check.
3. Read only what a failure or a doc update needs — the `## Context` map of the task involved names
   the template sections, memories and code anchors for it.

## Part 1 — make the feature green

1. **Build** the whole solution, test projects included.
2. **Run the whole test suite** — not only the feature's tests: the feature may have broken older ones.
3. **Check coverage of the contract.** Every row of every task's `## Test Cases` table must exist as a
   real test in the file it names. A missing row is a gate failure, not a pass — write the test.
4. **Fix every failure at its cause:**
   - The production code contradicts its task's Changes / Test Cases / Acceptance Criteria → fix the
     code. This is the normal case.
   - The test itself is wrong against its own Test Cases row (a wrong mock setup, a typo in an
     expected value that the row states differently) → fix the test to match the row.
   - NEVER weaken, skip, ignore, delete, or loosen a test to get green, and never change an expected
     value away from what the task's Test Cases row states.
5. **Repeat** build + whole test suite until both are green.
6. If a failure cannot be fixed within the feature's scope — the task itself contradicts the spec or
   another task, or the fix needs a decision — stop: do NOT print the completion marker, and report the
   failing test, the command, its output, and the contradiction in your summary.

## Part 2 — record the feature's documentation, once

Only after Part 1 is green, so the docs describe the final code. Use the formats from `PROMT_AGENT.md`
("Documentation"); the notes are your source, the code is the truth where they disagree.

1. **Changelog** — APPEND one entry to `ai-flow/docs/CHANGELOG.md` (never replace):
   ```
   ## [datetime] - [feature] <Feature name>
   - Delivered: <per task, one line each, from the notes>
   - Files: <key files>
   - Verification: build + whole test suite green; failures found and fixed (test → cause → fix),
     missing tests written
   ---
   ```
2. **Feature spec** — ensure `ai-flow/docs/specs/<feature>/README.md` (target) exists, created from the
   DesignReview if missing; write `ai-flow/docs/specs/<feature>/IMPLEMENTED.md` (as-built: behavior, key
   files, decisions, deviations from the target — including what Part 1 fixed); add the feature to the
   index in `ai-flow/docs/specs/README.md`.
3. **Knowledge** — every pattern / domain rule the notes list becomes Serena memory
   (`write_memory(...)`, shapes from `PROMT_SERENA.md`) with the CLAUDE.md "Project knowledge" table in
   sync. Resolve every listed conflict: fix the memory / spec / code, or report it — never drop it.
4. **Other docs** — apply the notes' "Docs to update": the matching `ai-flow/docs/` files and memories
   (`architecture-overview`, `suggested-commands`, `build-and-verify`).

If a task of this feature was run on its own (`--task`) it already wrote its docs — refresh them rather
than duplicate them.

DO NOT git commit and do NOT move task files, `NOTES.md` or the feature folder — on success the
orchestrator archives the feature into `ai-flow/docs/tasks/done/` and commits.

## Completion

Print the marker ONLY when the whole solution builds, the whole test suite passes, and the feature's
docs are recorded. The marker is the promise that the feature is green and documented; the orchestrator
archives the feature on it.

When (and only when) that is true, print exactly:
<promise>COMPLETE</promise>
