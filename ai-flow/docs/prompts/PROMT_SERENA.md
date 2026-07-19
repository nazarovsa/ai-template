# PROMT_SERENA — Bootstrap persistent project knowledge (Serena)

You are bootstrapping persistent project knowledge for AI coding agents on this codebase.
Goal: populate Serena memories with project-specific patterns and wire them into **CLAUDE.md**
(the project's source-of-truth instructions file; `AGENTS.md` only redirects to it) with direct
`read_memory(...)` calls — not filename hints.

## Phase 1 — Discover patterns

Investigate the codebase systematically. Use Serena's tools (`get_symbols_overview`, `find_symbol`,
`search_for_pattern`, `list_dir`) — do not read every file blindly. For each category, find ≥3 real
examples before drawing a conclusion. If patterns conflict, note both and flag the inconsistency
instead of picking one.

Categories:
- Architecture & layering — module boundaries, dependency direction, where business logic lives
- Domain business rules — the actual rules/mechanics/economy: formulas, coefficients, thresholds,
  invariants, entity lifecycles, and where in the code each rule is enforced (this is the *rules
  themselves*, distinct from "how domain code is written", which is the architecture/domain-modeling
  category)
- Error handling — exception types, propagation, what gets logged vs rethrown
- Testing — framework, naming, structure (AAA/GWT), mocking conventions, location
- Naming — files, types, methods, variables — note deviations from language defaults
- Data access — ORM/query patterns, transaction boundaries, repository shape
- API design — request/response shapes, validation, versioning, auth flow
- Configuration & secrets — where they live, how loaded, env handling
- Logging & observability — logger setup, levels, structured fields, tracing
- Build & verify — exact commands for build, test, lint, typecheck (run them once to confirm they
  work — do not guess)
- Commit/PR conventions — branch naming, commit format, PR template

## Phase 2 — Decide what becomes a memory

A pattern qualifies only if ALL hold:
- Non-obvious from a quick code read
- Violating it causes real problems (broken builds, regressions, review rejection)
- Stable (won't change weekly)

Skip anything a linter/formatter enforces, anything language conventions already imply, and one-off
historical decisions with no ongoing consequence.

Besides *technical patterns*, capture **key domain business rules** as memory — the actual mechanics
(formulas, coefficients, thresholds, invariants, entity lifecycles, economy). Qualify them the same
way: non-obvious, stable, real cost when violated. Their trigger differs from `domain-modeling`: reach
for `domain-modeling` to learn *how domain code is written*, and for `domain-rules` to learn or change
*the rule itself*. Keep the rule and its enforcing code in sync — do not change one without the other.

Group memories by *task trigger*, not topic. Ask: "When would the agent need this?" Aim for 5–10
memories total, each ≤80 lines. Do NOT overwrite the shipped memories `suggested-commands` and
`task-completion` — extend them if needed. Suggested triggers (drop any that don't apply, add others):
- architecture-overview — before structural changes
- domain-rules — the domain's business rules/mechanics: formulas, coefficients, invariants, economy
- auth-conventions — when touching auth code
- testing-patterns — before writing/modifying tests
- db-access-rules — when adding queries or migrations
- api-conventions — when adding/modifying endpoints
- error-handling — for any non-trivial change
- build-and-verify — before declaring work done

## Phase 3 — Write the memories

For each memory, use this structure, then save with `write_memory("<name>", "<content>")`:

# <Name>

## When to consult
<1–2 lines: which tasks trigger this read>

## Rules
- <Concrete, enforceable statement, with file:line reference where possible>

## Canonical examples in this codebase
- <path/to/file.ext> — <what makes it canonical>

## Anti-patterns
- <What NOT to do, with the reason>

For a **domain business-rule** memory (e.g. `domain-rules`), use this knowledge-shaped variant instead
— it captures the rule, not a coding convention, so `Rationale` + `Source of truth` replace
`Anti-patterns`:

# <Name>

## When to consult
<1–2 lines: which tasks need the rule itself>

## Rules & mechanics
- <Rule in plain words> → <formula> → <concrete values/thresholds> → <invariants it must uphold>

## Rationale / why
- <Why the rule exists — the intent behind the number/formula>

## Source of truth
- <spec path> — where it's specified; <path/to/file.ext:line> — where the code enforces it

## Phase 4 — Update CLAUDE.md

Add (or replace) the "Project knowledge (Serena memories)" section using direct tool calls. Keep the
"Always available" line for the shipped `suggested-commands` / `task-completion` memories; the trigger
table below lists ONLY the project-specific memories you created (one row per created memory). Format:

## Project knowledge (Serena memories)

Run `list_memories` at session start to confirm what's available.

Mandatory reads — call BEFORE the matching task:

| Task trigger | Required call |
|---|---|
| Structural changes, new modules | `read_memory("architecture-overview")` |
| Domain rules, formulas, invariants, economy | `read_memory("domain-rules")` |
| Touching auth/authz code | `read_memory("auth-conventions")` |
| Writing or modifying tests | `read_memory("testing-patterns")` |
| Adding DB queries or migrations | `read_memory("db-access-rules")` |
| Adding/modifying HTTP endpoints | `read_memory("api-conventions")` |
| Verifying work is done | `read_memory("build-and-verify")` |

After establishing a new pattern or correcting an outdated one, update with `write_memory(...)`.
Do not silently diverge from a memory — fix the memory or escalate the conflict.

Use the actual memory names you created. Drop rows whose memory you didn't create. No placeholders.

## Phase 4b — Project overview (onboarding only)

Fill **only** the Overview + Capabilities in `ai-flow/docs/specs/README.md` from what you discovered.
Do NOT create per-feature spec folders — those are added automatically as features are implemented
through the flow (`specs/<feature>/README.md` target + `IMPLEMENTED.md` as-built).

## Phase 5 — Self-check before reporting done

1. Every memory written is referenced from CLAUDE.md (no orphans).
2. Every CLAUDE.md row points to an existing memory — verify with `list_memories`.
3. Each memory contains ≥1 concrete codebase reference, not just abstract rules.
4. No memory duplicates another memory's content.
5. Build/test commands in `build-and-verify` were actually executed and confirmed.

## Final report

- Memories created: list with one-line summaries
- CLAUDE.md diff
- Pattern conflicts found in the codebase that the team should resolve
