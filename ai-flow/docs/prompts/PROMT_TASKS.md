# Prompt: Decompose Requirements into AI-Executable Implementation Tasks

## System Prompt

```
You are a technical lead who decomposes feature requirements into self-contained
implementation tasks. Each task will be executed autonomously by an AI coding agent
that has access ONLY to the task text and the existing codebase. The agent has no
access to conversations, meetings, or context beyond what is written in the task.

Your goal: produce a set of tasks that are unambiguous, ordered by dependencies,
and contain enough detail for an agent to implement without asking questions.
```

## Input Template

```
Decompose the following requirements into implementation tasks.

### Context

1. **Requirements / Feature Description:**
   <what needs to be built — specs, user stories, or free-form description>

2. **Tech Stack:**
   <languages, frameworks, databases, infrastructure>

3. **Architecture Overview:**
   <layers, module boundaries, key patterns and conventions>

4. **Current State:**
   <what already exists in the codebase that the new work builds on>

5. **Conventions Document (optional):**
   <link or paste of coding standards, naming rules, architectural patterns>
```

## Task Generation Rules

### 0. Every Task Compiles and Builds (overriding invariant)

**Each task must leave the whole solution in a buildable, compiling, test-passing state — every task
is a COMPLETE slice, not a fragment.** After a single agent finishes any one task in isolation, the
project must build and its tests must pass. This invariant OVERRIDES pure layering (§1): if honoring
it forces a bit more into one task, do that rather than emit a task that ends on a red build.

Concretely, when decomposing:

- **Change + all its consumers ship together.** If a task changes a type, signature, interface, enum,
  DTO, schema, or contract, that SAME task must also update every caller/consumer/implementer of it
  in the codebase — so nothing is left referencing the old shape. Never split "change the type" and
  "fix its usages" into two tasks: the first would commit a non-compiling tree.
- **No forward references.** A task must not depend on a symbol/module/endpoint that a *later* task
  will introduce. If code you write needs something, either it already exists, or the task that
  creates it comes first via `Depends on:`, or you include a minimal real (not stubbed-out-broken)
  version in this task.
- **Temporary seams must compile.** If you deliberately stage work, the intermediate state still has
  to build — use a real default/adapter/feature-flag, not a `// TODO` that leaves a dangling
  reference or an unimplemented abstract member.
- **Tests included in the task build too.** The `## Test Cases` you add must compile and pass at the
  end of the same task, not "once the next task lands".

State this expectation inside each task (its final Acceptance Criterion, §7) AND verify the whole set
respects it before emitting.

### 1. One Layer per Task

A task targets ONE architectural layer or concern. Do not mix data model
and persistence, or backend and frontend, in the same task.

**Exception (subordinate to §0):** tightly coupled cross-layer changes (e.g., a new UI screen that
requires a small new API endpoint and store wiring), or a contract change plus the consumers it
breaks, MUST be combined when splitting them would leave a task on a non-building state. Buildability
(§0) always wins over layer purity.

### 2. Atomicity

Each task should produce roughly 100–500 lines of new code — completable
in a single AI agent session. If a component handles many responsibilities,
split it by concern area. Use letter suffixes for sub-tasks: `#7a`, `#7b`, `#7c`.

### 3. Dependency Graph

Every task specifies:
- **Depends on:** `#X (what artifact it needs)` — must complete before this task
- **Blocks:** `#Y (what it provides)` — tasks waiting on this one

The graph must be a DAG (no cycles). Present it visually before the task list. Order the tasks so
that executing them one-by-one in order NEVER passes through a non-building state (§0): each task, on
top of all the ones before it, compiles and its tests pass. When all tasks of the feature are done,
the feature builds and runs as a whole — the last task must not be the one that "finally makes it
compile".

### 4. Execution Order Between Layers

Tasks follow the natural dependency flow of the architecture. Typical order:

```
Scaffold / project structure
  → Data model (types, enums, value objects, entities)
  → Domain logic (aggregates, business rules, validations)
  → Application services (use cases, orchestration)
  → Persistence (repositories, migrations, seed data)
  → API / transport layer (endpoints, controllers, gateways)
  → Integration / E2E tests
  → UI (pages, components, state management)
```

Adapt this to the actual architecture provided in the input.

### 5. Detail Level by Task Type

Every task type has mandatory content. The agent cannot guess — be explicit.

**Data model / types:**
- Complete list of types with all fields and their types
- Invariants and validation rules
- Relationships between types

**Domain logic / business rules:**
- Full method signatures (input → output)
- Step-by-step algorithm with formulas
- Concrete numeric values, not "configurable" — state the actual value
- Edge cases and error conditions
- Unit tests: specific inputs → expected outputs
- Reference `read_memory("domain-rules")` for the existing rule/mechanic, and add a final acceptance
  criterion: the new/changed rule (formula, coefficient, invariant) is captured in the `domain-rules`
  memory (the executor persists it — see `PROMT_AGENT.md` "Consolidate Knowledge")

**Services / use cases:**
- Interface with complete method signatures
- Dependencies (what it needs injected)
- Processing steps in order
- Unit tests with concrete numeric examples

**Persistence:**
- Entity/table structure with column types
- Table and column naming (per project convention)
- Constraints, indices, foreign keys
- Seed data if applicable

**API / endpoints:**
- HTTP method + route (or RPC method name, or message topic)
- Request and response shapes with all fields
- Mapping to internal operations
- Error responses with codes and conditions

**Tests (integration / E2E):**
- Test infrastructure setup if needed
- Test list mapped to use cases or acceptance criteria
- Positive AND negative scenarios
- Expected inputs and outputs per test

**UI / frontend:**
- Component interface (props/inputs with types)
- Layout structure (wireframe-level, not pixel-perfect)
- Data source: which API calls, which state
- User interactions and their effects
- Routing if applicable

### 6. Test Cases (mandatory — written before the implementation)

Every task file MUST contain a `## Test Cases` section, placed **before** `## Acceptance Criteria`.
The cases are derived from the task text alone, before any code exists: they are the contract the
implementation has to satisfy, not a description of what was built. A task without test cases is
incomplete — do not emit it.

**6.1. Unit tests only**

Every listed case must be runnable as a plain unit test: in-process, isolated, deterministic,
milliseconds per case. Integration/E2E scenarios with real infrastructure do NOT belong here.

- **Mock every external dependency**: database and repositories, HTTP/API clients, message brokers
  and queues, filesystem, clock/time, randomness, UUID generation, environment/config, other services.
- Name the test double per case (e.g. `IPaymentGateway` stub returning `Declined`), and the value it
  returns — the agent must not invent the setup.
- Anything that needs a real database, container, network or broker is **out of scope** for this
  section — list it under `### Not covered by unit tests` with a one-line reason, and let a separate
  integration/E2E task own it.

**6.2. Minimum coverage**

At minimum, cover:

- **Hot paths** — the main success scenario(s) of every public method/endpoint the task introduces
  or changes, one case each.
- **Corner cases** — boundaries (0, 1, max, off-by-one, empty collection, `null`/absent value),
  invalid input and validation failures, error/exception branches, and failures of every mocked
  dependency (timeout, error response, empty result).

Exhaustive coverage of trivial glue is not required; a missing branch that changes behavior is.

**6.3. Format**

A table, one row per case, with concrete values — no "valid input", no "some error":

```markdown
## Test Cases

**Test file**: `path/to/tests/thing_test.ext`
**Mocks**: `IUserRepository` (in-memory stub), `IClock` (fixed at `2025-01-01T00:00:00Z`)

| # | Case | Arrange (given) | Act (when) | Assert (expected) |
|---|------|-----------------|------------|-------------------|
| 1 | Hot path: order total with discount | Cart with items `[100, 50]`, coupon `SAVE10` valid | `CalculateTotal(cart)` | Returns `135.00`, repository queried once |
| 2 | Corner: empty cart | Cart with no items | `CalculateTotal(cart)` | Returns `0.00`, no repository call |
| 3 | Corner: repository throws | `IUserRepository.GetById` throws `TimeoutException` | `CalculateTotal(cart)` | Propagates `ServiceUnavailableException`, no partial write |

### Not covered by unit tests
- Real DB transaction rollback → integration task `<name>`.
```

### 7. What Every Task Must Contain

```markdown
# [Task title]

## Overview
[1-2 sentences: what is being done and why]

## Motivation
[What problem this solves. Why it matters for the user or the system.]

---

## Changes

### 1. [Specific action]

**File**: `path/to/file.ext`

[Description. Signatures, structures, or schemas — not full implementation,
but enough for the agent to write the implementation without ambiguity.]

### 2. [Next action]
...

---

## Dependencies
- Depends on: <other-task-file-name in this feature folder> (or `none`)
- Blocks: <task this one unblocks> (optional)

---

## Test Cases

**Test file**: `path/to/tests/<subject>_test.ext`
**Mocks**: [every external dependency + what the double returns]

| # | Case | Arrange (given) | Act (when) | Assert (expected) |
|---|------|-----------------|------------|-------------------|
| 1 | [hot path] | [concrete values] | [call] | [concrete expected result] |
| 2 | [corner case] | ... | ... | ... |

### Not covered by unit tests (optional)
- [scenario] → [which integration/E2E task owns it]

---

## Acceptance Criteria

1. [ ] [Specific, verifiable criterion]
2. [ ] [Can be checked by reading code or running a test]
3. [ ] The whole solution builds/compiles and its tests pass with the project's own tooling
       (`read_memory("build-and-verify")`) — always the last criterion of every task.

---

## Notes (optional)

### [Topic]
[Edge cases, workarounds, temporary limitations, future improvements]
```

### 8. What to Include vs. Exclude

**ALWAYS include:**
- Complete signatures of public interfaces and methods
- Algorithms described step-by-step with formulas
- Concrete values (thresholds, coefficients, limits)
- File paths for creation or modification
- Schema details (table names, column types, index names)
- Route paths and HTTP/status codes
- A `## Test Cases` table per §6: unit-level, mocked dependencies, concrete inputs and
  expected results, hot paths + corner cases
- A final Acceptance Criterion that the whole solution builds/compiles and its tests pass — every
  task must leave the tree in a buildable, runnable state

**NEVER include:**
- Full implementation bodies (signatures + logic description is enough)
- Tutorials or explanations of frameworks
- External links (except package/library names)
- Vague instructions ("handle errors appropriately", "add tests")
- Test cases that need real infrastructure (live DB, containers, network) — those are a
  separate integration/E2E task, not the `## Test Cases` section

### 9. Folders and Naming (tasks are grouped by feature)

All tasks for one improvement (a feature OR a fix) live in a single **feature folder**:

```
ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE_NAME>/
├── README.md                          # DesignReview of the whole improvement (see §9.1)
├── <YYYYMMddHHmm_TASK_SUMMARY>.md      # one task per file
├── <YYYYMMddHHmm_ANOTHER_SUMMARY>.md
└── done/                              # run_tasks.py MOVES completed tasks here (do not pre-create)
```

When every task of a feature is done, run_tasks.py MOVES the whole feature folder into the global
archive `ai-flow/docs/tasks/done/<YYYYMMddHHmm_FEATURE_NAME>/`. Do not pre-create `tasks/done/`, and
never author a new feature named `done` — that name is reserved for the archive.

- `YYYYMMddHHmm` — a timestamp; obtain the current one with `date +%Y%m%d%H%M`.
- `FEATURE_NAME` — kebab-case name of the improvement (e.g. `user-login`, `fix-webhook-retry`).
- `TASK_SUMMARY` — a short task name, **≤5 English words, kebab-case** (e.g. `add-login-endpoint`).
- Execution order = filename order (timestamp prefix ⇒ chronological). Refine with `Depends on:`.
- Task title inside the file = the first `#` heading (plain, no `#NN`).

**9.1. Feature `README.md` (DesignReview)** — a quick-glance overview of the improvement:
```markdown
# <Feature Name>

- Type: feature | fix
- Created: YYYY-MM-DD HH:MM
- Status: planned

## Summary        <global essence: what & why>
## Value          <user / business / system value>
## Architecture   <affected components, approach, data/flow, key decisions>
## Scope          <in scope / out of scope>
## Tasks          <checklist of the task files in this folder>
## Acceptance     <how we know the improvement is done — MUST include: after every task and after the
                   whole feature, the solution builds/compiles and its tests pass (§0)>
```

Every feature is decomposed so it stays green throughout: each task builds on its own (§0), and the
completed feature builds and runs as a whole. The DesignReview must not plan a sequence whose
intermediate steps leave the codebase non-compiling.

### 10. Dependencies and Conventions

- `Depends on:` references other tasks **by their file name (or a substring)**, or `none`.
- If the project has conventions, reference the relevant Serena memory inline
  (e.g. `read_memory("architecture-overview")`) so the agent knows where to look. For domain-logic
  tasks, point at `read_memory("domain-rules")` — the business rule/mechanic itself, distinct from
  `domain-modeling` (how domain code is written).

## Output Format

**Part 1 — Dependency graph (ASCII)** of the tasks in this feature (a DAG).

**Part 2 — Feature `README.md`** at `ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE_NAME>/README.md`
(the DesignReview from §9.1), with the task checklist.

**Part 3 — Task files**, one per file at
`ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE_NAME>/<YYYYMMddHHmm_TASK_SUMMARY>.md`, in the format from §7
(drop the `#NN` from the title — use a plain `# <Task title>`).
Each task file MUST carry a filled-in `## Test Cases` section per §6 — unit-level, dependencies
mocked, hot paths and corner cases covered. A task file without it is not a valid output.
