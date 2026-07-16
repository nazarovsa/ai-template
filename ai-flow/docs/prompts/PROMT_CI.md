# Prompt: Port the ai-flow CI pipeline to another CI system

## System Prompt

```
You are a CI/CD engineer. You port an existing, working pipeline to another CI system without
changing what it does. The reference implementation is GitHub Actions; the orchestrator it drives
(ai-flow/run_tasks.py) is CI-agnostic and MUST NOT be modified — every difference between CI systems
belongs in the pipeline file, never in the orchestrator.

You do not invent syntax. Before writing a pipeline for a target you have not verified in this
session, read that system's current documentation and confirm every keyword you use: trigger and
manual-run syntax, typed input parameters, secret injection, per-step conditionals, artifact/step
outputs, concurrency control, and the CLI or API call that opens a merge/pull request. If the docs
contradict what you remember, the docs win. If you cannot verify a keyword, say so in the final
report instead of guessing.
```

## Input Template

```
Port the ai-flow CI pipeline to the following CI system.

1. **Target CI:** <GitLab CI / Bitbucket Pipelines / Azure DevOps / Jenkins / Gitea Actions / …>
2. **Self-hosted or SaaS:** <affects runner images, network access, secret storage>
3. **Runner / image constraints:** <default image, whether it has git/node/python, network egress>
4. **Review target:** <default branch that the merge/pull request is opened against>
5. **Keep the GitHub Actions workflow?** <yes = both live side by side / no = replace it>
```

## Reference implementation — read it first

`.github/workflows/ai-flow-tasks.yml` is the source of truth for **behavior**. Read it in full before
writing anything. Also read `ai-flow/run_tasks.py` (what it does with git, exit codes, and task files)
and the "Запуск задач в GitHub Actions" section of `README.md` (the operator-facing contract).

## Invariants — port these exactly

Each was established deliberately. If the target CI cannot express one, do NOT silently drop it:
implement the closest equivalent and record the gap in the final report.

1. **Run from the repository root.** Claude Code auto-discovers `CLAUDE.md`, `.claude/agents/`,
   `.claude/skills/` and `.claude/settings.json` from the *working directory*. A pipeline that runs
   steps from a subdirectory silently loses the project's rules and subagents.
2. **Never pass `--bare` to the agent.** Bare mode skips exactly that auto-discovery **and** ignores
   `CLAUDE_CODE_OAUTH_TOKEN`, so it breaks both the rules and the authentication.
3. **Authenticate with the `CLAUDE_CODE_OAUTH_TOKEN` secret** (from `claude setup-token`; requires a
   Pro/Max/Team/Enterprise subscription). Fail fast with an actionable message when it is absent.
   Do **not** set `ANTHROPIC_API_KEY` in the job: it outranks the OAuth token in Claude Code's
   authentication precedence and would silently switch billing to per-token API usage.
4. **Toolchain:** Node.js 22+ and `npm install -g @anthropic-ai/claude-code`, plus Python 3.12 and
   `pyyaml` (the orchestrator's only dependency). Python must be on `PATH` as `python`, because
   `.claude/settings.json` registers a SessionStart hook that invokes it.
5. **Isolate the run on its own branch** cut from the commit being built, named after the run
   (`ai-flow/run-<run-id>`), so a failed run never touches the review target.
6. **The orchestrator commits, the pipeline does not.** `run_tasks.py` moves each finished task into
   the feature's `done/` folder and commits it. The pipeline only configures a git identity, pushes,
   and opens the merge/pull request.
7. **An empty task queue is a success, not a failure.** `run_tasks.py` exits 1 when it finds no tasks
   at all, which would otherwise paint a fresh repo's first run red. Count pending tasks first and
   skip the run cleanly. Reuse the orchestrator's own parser rather than reimplementing the layout:

   ```python
   import sys
   sys.path.insert(0, "ai-flow")
   import run_tasks as rt
   cfg = rt.load_config(rt.DEFAULT_CONFIG)
   tasks_dir = (cfg.get("context") or {}).get("tasks_dir", "ai-flow/docs/tasks")
   print(len(rt.pending_tasks(rt.resolve(tasks_dir))))
   ```
8. **Preserve partial results.** If the orchestrator fails partway, still open the merge/pull request
   for the tasks that completed, warn about it in the description, and mark the run failed.
9. **Serialize concurrent runs** on the same branch — tasks move shared files.
10. **Manual trigger with the same parameters:** `feature`, `task`, `agent`, `model`, `dry_run`,
    `draft_pr` — mapped onto `run_tasks.py`'s flags (`--feature`, `--task`, `--agent`, `--model`,
    `--dry-run`). Empty means "not passed", not an empty string argument.
11. **Only the `claude` agent is installed.** Offer no agent choice the pipeline cannot actually run;
    document how to add `codex`/`zcode`.
12. **Never interpolate a user-supplied parameter into a shell command.** Pass it through the
    environment and quote it, so a crafted parameter cannot inject shell code.

## Target-specific translation

Work out each of these from the target's documentation, not from analogy:

| Concern | GitHub Actions reference | Find the target's equivalent |
|---|---|---|
| Manual run with typed inputs | `workflow_dispatch.inputs` | e.g. GitLab `workflow:rules` + `spec:inputs` / manual job variables |
| Secret injection | `secrets.CLAUDE_CODE_OAUTH_TOKEN` | masked/protected CI variable, vault binding |
| Step conditional | `if: steps.x.outputs.y == 'true'` | `rules:`, `when:`, stage gating |
| Value passed between steps | `$GITHUB_OUTPUT` | `dotenv` artifacts, exported variables, files |
| Serialization | `concurrency.group` | `resource_group`, queue settings |
| Push credential | `GITHUB_TOKEN` | deploy key, project access token, `CI_JOB_TOKEN` |
| Open the review request | `gh pr create` | `glab mr create`, REST API call, push options |
| Human-readable summary | `$GITHUB_STEP_SUMMARY` | job log, MR description, artifact |

Watch for shell semantics: the reference relies on `bash` with `-e`, where `[ -n "$X" ] && cmd`
**aborts the step** when `X` is empty. Use explicit `if` blocks. Also note that in GitHub Actions a
skipped step yields an *empty* output, so conditions compare against an explicit flag rather than
`!= '0'` — check whether the target has the same trap.

Prefer the target's native credential for pushing. If it must be a token, warn in the docs when that
token cannot trigger downstream pipelines (GitHub's `GITHUB_TOKEN` and GitLab's `CI_JOB_TOKEN` both
have this limitation).

## Output

1. **The pipeline file**, at the target's conventional path (GitLab → `.gitlab-ci.yml`; Bitbucket →
   `bitbucket-pipelines.yml`; Azure DevOps → `azure-pipelines.yml`; Jenkins → `Jenkinsfile`). If the
   repository already has one, **merge** into it — do not overwrite a user's existing pipeline.
2. **A header comment** in that file covering: what it does, the root-directory requirement, the
   `--bare` prohibition, and how to obtain and store the token.
3. **`ai-flow/init.py`** — add the new file to `MANIFEST` so the installer deploys it.
4. **`README.md`** — a subsection alongside "Запуск задач в GitHub Actions" with: how to get the
   token, where to put the secret, how to trigger a run, the parameter table, and the target's own
   pitfalls. Match the README's language and tone.
5. **`CLAUDE.md`** — extend the CI line in "Workflow" to name the new pipeline file.

## Self-check before reporting done

1. Every keyword used is confirmed against the target's current documentation — no keyword recalled
   from memory alone.
2. The pipeline file parses (run the target's linter if one exists, e.g. `glab ci lint`; otherwise at
   minimum validate it as YAML).
3. Walk all four paths and confirm the outcome of each: **no pending tasks** (green, no MR) ·
   **tasks succeed** (green, MR with the task list) · **orchestrator fails partway** (red, MR with a
   warning) · **`dry_run`** (green, no commits, no MR).
4. Every step that consumes a parameter reads it from the environment, quoted — grep the file to
   confirm no parameter is interpolated into a command string.
5. `run_tasks.py` is unmodified — `git diff` it to be sure.
6. Each of the 12 invariants is either implemented or listed as a gap in the report.

## Final report

- Pipeline file created/merged, and the trigger to use
- Invariant-by-invariant mapping: how each was expressed in the target
- Gaps: invariants the target cannot express, and the chosen fallback
- Anything you could not verify against documentation, stated plainly as unverified
- Setup the operator must still do by hand (secrets, runner image, branch protections)
