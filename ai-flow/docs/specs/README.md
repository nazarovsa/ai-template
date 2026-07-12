# <Project> — Specs & Functionality

> Project specifications **and** living functionality docs — one place, no duplication.
> **Onboarding fills only the Overview / Capabilities below.** Per-feature specs are added
> automatically as features are implemented.

## Overview

<General project description: purpose, domain, high-level architecture. Filled during onboarding
by `doc-keeper` / `PROMT_SERENA`.>

## Capabilities

<Bullet list of what the project currently does.>

## Structure

```
ai-flow/docs/specs/
├── README.md                       # this file (project overview + index)
├── NN-<area>.md                    # optional broad context specs (from PROMT_SPEC)
└── <YYYYMMddHHmm_FEATURE>/         # per-feature spec, mirrors tasks/<feature>/
    ├── README.md                   #   target — what the feature should do
    └── IMPLEMENTED.md              #   as-built — what was actually implemented
```

- `run_tasks.py` injects these as pointers; the agent reads the relevant ones.
- Broad context specs are generated via `../prompts/PROMT_SPEC.md`.
- Per-feature `README.md` (target) + `IMPLEMENTED.md` (as-built) are kept current automatically
  after tasks run (see `../prompts/PROMT_AGENT.md`).

## Feature index

<!-- Added automatically as features ship, mirroring ai-flow/docs/tasks/<feature>/:
- [YYYYMMddHHmm_FEATURE_NAME](./YYYYMMddHHmm_FEATURE_NAME/README.md) — one-line summary
-->
