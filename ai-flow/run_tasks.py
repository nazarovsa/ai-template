#!/usr/bin/env python3
"""
Automated task executor (multi-agent).

Layout:
    Flow infrastructure lives in `ai-flow/`. The project root is its parent
    (REPO_ROOT). Task/spec artifacts live under `ai-flow/docs/`, Serena memory
    lives in `<REPO_ROOT>/.serena/memories/`. The agent runs with cwd = REPO_ROOT
    so it sees and edits the whole project, not just `ai-flow/`.

Tasks are grouped by feature. Each feature is a folder; each task is a file inside it:
    ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/README.md              # DesignReview of the feature
    ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/<YYYYMMddHHmm_TASK>.md  # a task
On completion a task file is MOVED to the feature's done/ subfolder:
    ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/done/<...>.md
When ALL tasks of a feature are done, the whole feature folder is MOVED into the
global done/ catalog (archive of fully completed features):
    ai-flow/docs/tasks/done/<YYYYMMddHHmm_FEATURE>/
Pending tasks run in filename order (timestamp prefix => chronological); explicit
`Depends on:` lines gate ordering. `README.md` inside a feature folder is not a task.

Test gate (`test_gate` in agents.yml) — the green-tests gate applies to the unit of work requested:
    feature (default) — a feature run (no --task) tells each task agent to write its tests (TDD) and
        make the solution compile, but NOT to run the tests. Once a feature has no pending tasks, a
        verification pass (PROMT_VERIFY.md) builds the solution, runs the whole test suite and fixes
        failures; only a green pass archives the feature. A feature whose tasks are all in done/ but
        which is not archived yet is unverified, and is verified first on the next run. A --task run
        is a single-task unit: that task runs its tests itself.
    task — every task builds and runs the tests; features are archived right after their last task.

Agents are configured in `ai-flow/agents.yml`; the template ships `claude` only (another
agentic CLI adds its own entry — see ai-flow/docs/prompts/PROMT_TOOL.md). The prompt is
piped via stdin, unless the agent command contains the `{prompt_file}` placeholder — then
the prompt is written to a temp file whose path is substituted into the command (paths with
spaces must be quoted in the command template itself). The completion marker (default
<promise>COMPLETE</promise>) and per-task timeout come from the config.

Usage:
    python ai-flow/run_tasks.py                      # default agent from agents.yml
    python ai-flow/run_tasks.py --agent claude --model sonnet   # override agent / model
    python ai-flow/run_tasks.py --feature user-login # only tasks in matching feature folders
    python ai-flow/run_tasks.py --task add-login     # only tasks whose name matches
    python ai-flow/run_tasks.py --dry-run            # show the plan without executing
    python ai-flow/run_tasks.py --config path.yml    # custom config
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install it with:  pip install pyyaml")
    sys.exit(1)

FLOW_DIR = Path(__file__).resolve().parent
REPO_ROOT = FLOW_DIR.parent
DEFAULT_CONFIG = FLOW_DIR / "agents.yml"

COMMIT_MAX_LEN = 155  # commit message limit (see CLAUDE.md)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: Path) -> dict:
    if not path.exists():
        print(f"ERROR: config not found: {path}")
        sys.exit(1)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve(rel: str) -> Path:
    """Resolve a config-relative path against REPO_ROOT."""
    return (REPO_ROOT / rel).resolve()


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class Task:
    id: str          # filename stem, e.g. "202607121430_add-login-endpoint"
    feature: str     # feature folder name, e.g. "202607121430_user-login"
    title: str
    content: str
    deps: list[str] = field(default_factory=list)
    file: Path | None = None


# ---------------------------------------------------------------------------
# Task discovery — tasks live in feature folders; completed tasks move to done/
#   ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/<YYYYMMddHHmm_TASK>.md
#   ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/done/<...>.md   (completed task)
#   ai-flow/docs/tasks/done/<YYYYMMddHHmm_FEATURE>/           (fully completed feature)
# ---------------------------------------------------------------------------

DONE_DIR = "done"  # both the per-feature done/ subfolder and the global done/ catalog


def _feature_dirs(tasks_dir: Path) -> list[Path]:
    """Active (not fully completed) feature folders. Excludes the global done/ catalog."""
    if not tasks_dir.exists():
        return []
    return [d for d in sorted(tasks_dir.iterdir())
            if d.is_dir() and not d.name.startswith(".") and d.name != DONE_DIR]


def _archived_feature_dirs(tasks_dir: Path) -> list[Path]:
    """Feature folders archived into the global done/ catalog (fully completed features)."""
    catalog = tasks_dir / DONE_DIR
    if not catalog.exists():
        return []
    return [d for d in sorted(catalog.iterdir()) if d.is_dir() and not d.name.startswith(".")]


def _parse_deps(content: str) -> list[str]:
    m = re.search(r"(?:\*\*)?(?:Depends on|Зависит от):(?:\*\*)?\s*(.+)", content)
    if not m:
        return []
    raw = m.group(1).strip()
    if raw.lower() in ("none", "нет", "-", ""):
        return []
    toks = re.split(r"[,\s]+", raw)
    return [t.lstrip("#").strip() for t in toks
            if t.strip() and t.strip().lower() not in ("none", "нет", "-")]


def completed_stems(tasks_dir: Path) -> set[str]:
    done: set[str] = set()
    for feat in _feature_dirs(tasks_dir) + _archived_feature_dirs(tasks_dir):
        dd = feat / DONE_DIR
        if dd.exists():
            done |= {p.stem for p in dd.glob("*.md")}
    return done


def _dep_satisfied(dep: str, completed: set[str]) -> bool:
    dep = dep.lower()
    return any(dep == c.lower() or dep in c.lower() for c in completed)


def pending_tasks(tasks_dir: Path) -> list[Task]:
    tasks = []
    for feat in _feature_dirs(tasks_dir):
        for path in sorted(feat.glob("*.md")):
            if path.stem.lower() == "readme":
                continue
            content = path.read_text(encoding="utf-8")
            tasks.append(Task(
                id=path.stem, feature=feat.name,
                title=_first_heading(content) or path.stem,
                content=content, deps=_parse_deps(content), file=path,
            ))
    tasks.sort(key=lambda t: (t.feature, t.id))  # timestamp prefixes sort chronologically
    return tasks


def feature_readme(tasks_dir: Path, feature: str) -> str:
    for name in ("README.md", "readme.md"):
        p = tasks_dir / feature / name
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""


def mark_done(task: Task) -> None:
    assert task.file is not None
    dest = task.file.parent / DONE_DIR
    dest.mkdir(exist_ok=True)
    new_path = dest / task.file.name
    task.file.rename(new_path)
    task.file = new_path
    print(f"  -> {task.feature}/{DONE_DIR}/{new_path.name}")


def _has_pending_tasks(feature_dir: Path) -> bool:
    """A feature is still active while any task file remains at its top level (README excluded)."""
    return any(p.stem.lower() != "readme" for p in feature_dir.glob("*.md"))


def archive_feature_if_complete(tasks_dir: Path, feature: str) -> None:
    """Once every task of a feature is done, move the whole feature folder into done/."""
    feature_dir = tasks_dir / feature
    if not feature_dir.exists() or _has_pending_tasks(feature_dir):
        return
    catalog = tasks_dir / DONE_DIR
    catalog.mkdir(exist_ok=True)
    feature_dir.rename(catalog / feature)
    print(f"  ==> feature complete: {feature}/ -> {DONE_DIR}/{feature}/")


def unverified_features(tasks_dir: Path) -> list[str]:
    """Active features whose tasks are all in done/ — they still await the verification pass."""
    return [d.name for d in _feature_dirs(tasks_dir)
            if not _has_pending_tasks(d) and any((d / DONE_DIR).glob("*.md"))]


def feature_done_tasks(tasks_dir: Path, feature: str) -> list[Path]:
    return sorted((tasks_dir / feature / DONE_DIR).glob("*.md"))


# ---------------------------------------------------------------------------
# Context loaders
# ---------------------------------------------------------------------------

def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_claude_md() -> str:
    content = _load_text(REPO_ROOT / "CLAUDE.md")
    return f"## Project Rules (CLAUDE.md)\n\n{content}" if content else ""


def _load_specs_summary(specs_dir: Path) -> str:
    if not specs_dir.exists():
        return ""
    rel = specs_dir.relative_to(REPO_ROOT)
    files = [s for s in sorted(specs_dir.glob("*.md")) if s.name.lower() != "readme.md"]
    feature_dirs = [d for d in sorted(specs_dir.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if not files and not feature_dirs:
        return ""
    lines = [f"## Specs (in {rel.as_posix()}/) — read the relevant ones", ""]
    lines += [f"- `{(rel / s.name).as_posix()}`" for s in files]
    lines += [f"- `{(rel / d.name).as_posix()}/` (README target + IMPLEMENTED as-built)" for d in feature_dirs]
    return "\n".join(lines)


def _first_heading(md: str) -> str:
    for line in md.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return ""


def _load_memories(memories_dir: Path, *, inline: bool) -> str:
    if not memories_dir.exists():
        return ""
    files = sorted(memories_dir.glob("*.md"))
    if not files:
        return ""
    rel = memories_dir.relative_to(REPO_ROOT)
    if inline:
        sections = ["## Serena memories (full content)", ""]
        for f in files:
            sections.append(f"### {f.stem}")
            sections.append(_load_text(f).strip())
            sections.append("")
        return "\n".join(sections)
    # pointers only — the agent reads the ones it needs
    lines = [
        "## Serena memories (read the relevant ones before implementing)",
        f"Location: `{rel.as_posix()}/` — plain `.md` files, readable directly.",
        "",
    ]
    for f in files:
        lines.append(f"- `{f.stem}` — {_first_heading(_load_text(f)) or f.stem}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

def _is_git_repo() -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    return r.returncode == 0 and r.stdout.strip() == "true"


def _has_changes() -> bool:
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return bool(r.stdout.strip())


def commit_task(task: Task, git_cfg: dict) -> bool:
    template = git_cfg.get("message_template", "feat: task #{id} - {title}")
    return _commit(template.format(id=task.id, title=task.title), f"#{task.id}", git_cfg)


def commit_verification(feature: str, git_cfg: dict) -> bool:
    template = git_cfg.get("verify_message_template", "test: feature #{feature} - tests green")
    return _commit(template.format(feature=feature), f"feature {feature}", git_cfg)


def _commit(message: str, label: str, git_cfg: dict) -> bool:
    if not git_cfg.get("enabled", True) or not git_cfg.get("auto_commit", True):
        return True
    if not _is_git_repo():
        print("  [!] Not a git repository — skipping commit")
        return True
    subprocess.run(["git", "add", "-A"], cwd=REPO_ROOT, check=True)
    if not _has_changes():
        print(f"  [!] Nothing to commit for {label}")
        return True
    # Single line, <= COMMIT_MAX_LEN chars, no tool/AI mentions (see CLAUDE.md).
    msg = message.splitlines()[0][:COMMIT_MAX_LEN]
    result = subprocess.run(
        ["git", "commit", "-m", msg], cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"  [ok] {msg}")
        return True
    print(f"  [fail] Commit failed:\n{result.stderr}")
    return False


# ---------------------------------------------------------------------------
# Prompt + agent
# ---------------------------------------------------------------------------

def _ensure_changelog_file(changelog_file: Path) -> None:
    changelog_file.parent.mkdir(parents=True, exist_ok=True)
    if not changelog_file.exists():
        changelog_file.write_text(
            "# Changelog\n\n"
            "Chronological journal of completed tasks — each task run APPENDS an entry below.\n"
            "Reusable patterns are NOT recorded here: they live in Serena memory "
            "(`.serena/memories/*`) and are indexed in the CLAUDE.md \"Project knowledge\" table.\n\n"
            "---\n",
            encoding="utf-8",
        )


def _design_block(tasks_dir: Path, feature: str) -> str:
    design = feature_readme(tasks_dir, feature)
    return f"## Feature DesignReview ({feature}/README.md)\n\n{design}" if design else ""


def build_prompt(task: Task, ctx: dict, marker: str, *, defer_tests: bool) -> str:
    agent_prompt = _load_text(resolve(ctx["agent_prompt"]))
    claude_md = _load_claude_md()
    specs = _load_specs_summary(resolve(ctx["specs_dir"]))
    memories = _load_memories(resolve(ctx["memories_dir"]), inline=ctx.get("inline_memories", False))
    changelog = _load_text(resolve(ctx["changelog_file"]))
    design_block = _design_block(resolve(ctx["tasks_dir"]), task.feature)
    specs_dir = ctx["specs_dir"]

    if defer_tests:
        test_gate = ("feature — write this task's tests but do NOT run them; the feature verification "
                     "pass runs the whole suite after the feature's last task")
        gate_reminder = """- BLOCKING: build the whole solution, test projects included (read_memory("build-and-verify")) — it
  MUST compile. Write every Test Cases row as a real test (TDD) but do NOT run the test suite: the
  feature verification pass runs it once the feature's last task is done. If it does not compile, the
  task is NOT done — do NOT print the completion marker; report the failing command and its output."""
    else:
        test_gate = "task — build the solution and run its tests before finishing this task"
        gate_reminder = """- BLOCKING: build the whole project and run its tests (read_memory("build-and-verify")). The solution
  MUST compile/build and pass tests. If it does not build, the task is NOT done — do NOT print the
  completion marker; report the failing command and its output instead."""

    return f"""{agent_prompt}

---

{claude_md}

## Project context

Working directory: {REPO_ROOT}
Feature: {task.feature}
Test gate: {test_gate}

{specs}

{memories}

{design_block}

## Changelog (recent history)

{changelog or "(No previous entries)"}

---

## Task to implement

{task.content}

---

Remember:
- Read existing code before writing.
- Follow project rules (CLAUDE.md), the Feature DesignReview, and Serena memories.
{gate_reminder}
- Reusable patterns → document them as Serena memory (write_memory) + the CLAUDE.md table, NOT the changelog.
- APPEND a factual changelog entry (what changed + files) to `{ctx["changelog_file"]}`.
- Update the feature spec (living docs): ensure `{specs_dir}/{task.feature}/README.md` (target) exists
  and record what you built in `{specs_dir}/{task.feature}/IMPLEMENTED.md` (as-built).
- DO NOT git commit — the orchestrator handles commits.
- When done, print exactly: {marker}
"""


def build_verify_prompt(feature: str, ctx: dict, marker: str) -> str:
    verify_prompt = _load_text(resolve(ctx["verify_prompt"]))
    claude_md = _load_claude_md()
    specs = _load_specs_summary(resolve(ctx["specs_dir"]))
    memories = _load_memories(resolve(ctx["memories_dir"]), inline=ctx.get("inline_memories", False))
    tasks_dir = resolve(ctx["tasks_dir"])
    design_block = _design_block(tasks_dir, feature)
    task_list = "\n".join(
        f"- `{p.relative_to(REPO_ROOT).as_posix()}` — {_first_heading(_load_text(p)) or p.stem}"
        for p in feature_done_tasks(tasks_dir, feature)
    )

    return f"""{verify_prompt}

---

{claude_md}

## Project context

Working directory: {REPO_ROOT}
Feature: {feature}
Test gate: feature — this is the verification pass that closes it

{specs}

{memories}

{design_block}

## Tasks of this feature (implemented, tests written but not yet run)

{task_list}

Their changelog entries in `{ctx["changelog_file"]}` say what each task changed.

---

Remember:
- BLOCKING: build the whole solution and run the WHOLE test suite (read_memory("build-and-verify")).
  Fix every failure and re-run until green. Never weaken, skip, or delete a test to get green.
- Every Test Cases row of every task above must exist as a real test — write any that is missing.
- APPEND a changelog entry for this pass to `{ctx["changelog_file"]}`.
- DO NOT git commit and do NOT move task files — the orchestrator archives the feature and commits.
- Print exactly {marker} ONLY when the build and the whole test suite are green.
"""


def run_agent(task: Task, agent: dict, model: str, marker: str, timeout: int,
              *, dry_run: bool, ctx: dict, defer_tests: bool) -> bool:
    tests = "deferred to the feature verification pass" if defer_tests else "run by this task"
    return _invoke(
        f"  >>  [{task.feature}] {task.id}: {task.title}",
        [f"deps : {task.deps or 'none'}", f"tests: {tests}"],
        lambda: build_prompt(task, ctx, marker, defer_tests=defer_tests),
        agent, model, marker, timeout, dry_run=dry_run, ctx=ctx, strict=False,
    )


def run_verification(feature: str, agent: dict, model: str, marker: str, timeout: int,
                     *, dry_run: bool, ctx: dict) -> bool:
    # Strict: the pass IS the green-tests gate, so a missing marker is a failure even on exit 0.
    return _invoke(
        f"  ##  [{feature}] feature verification pass (build + whole test suite)",
        [],
        lambda: build_verify_prompt(feature, ctx, marker),
        agent, model, marker, timeout, dry_run=dry_run, ctx=ctx, strict=True,
    )


def _invoke(header: str, details: list[str], make_prompt, agent: dict, model: str, marker: str,
            timeout: int, *, dry_run: bool, ctx: dict, strict: bool) -> bool:
    command = agent["command"].replace("{model}", model)
    print(f"\n{'=' * 72}")
    print(header)
    for line in details:
        print(f"  {line}")
    print(f"  model: {model}")
    print(f"  cmd  : {command}")
    print(f"{'=' * 72}")

    if dry_run:
        print(f"  [dry-run] {command} < <prompt>  (cwd={REPO_ROOT})")
        return True

    _ensure_changelog_file(resolve(ctx["changelog_file"]))
    prompt = make_prompt()

    env = os.environ.copy()
    for k, v in (agent.get("env") or {}).items():
        env[k] = os.path.expandvars(str(v))

    tmp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False)
    proc = None
    try:
        tmp.write(prompt)
        tmp.close()

        if "{prompt_file}" in command:
            # Prompt is delivered as a file (a CLI that cannot read stdin): substitute the raw path —
            # the command template is responsible for quoting it.
            cmd = command.replace("{prompt_file}", tmp.name)
        else:
            cmd = f'{command} < "{tmp.name}"'
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            shell=True, text=True, encoding="utf-8", errors="replace",
            cwd=REPO_ROOT, env=env,
        )
        print("  ... agent started, streaming output...", flush=True)

        output_lines: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            output_lines.append(line)

        proc.wait(timeout=timeout)
        output = "".join(output_lines)

        if marker in output:
            return True
        if strict:
            print(f"  [fail] No completion marker (exit code {proc.returncode}) — the gate is not green")
            return False
        if proc.returncode == 0:
            print("  [!] No completion marker — treating exit 0 as success")
            return True
        print(f"  [fail] Exit code {proc.returncode}")
        return False

    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
        print(f"  [fail] Timed out after {timeout}s")
        return False
    except KeyboardInterrupt:
        if proc:
            proc.kill()
        print("\n  [!] Interrupted by user")
        raise
    finally:
        os.unlink(tmp.name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Automated multi-agent task executor.")
    parser.add_argument("--agent", help="agent name from agents.yml (default: config default_agent)")
    parser.add_argument("--model", help="override the agent model")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="path to agents.yml")
    parser.add_argument("--feature", help="run only tasks in this feature folder (name or substring)")
    parser.add_argument("--task", help="run only this task (stem or substring)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    ctx = {
        "tasks_dir": "ai-flow/docs/tasks",
        "specs_dir": "ai-flow/docs/specs",
        "memories_dir": ".serena/memories",
        "changelog_file": "ai-flow/docs/CHANGELOG.md",
        "agent_prompt": "ai-flow/docs/prompts/PROMT_AGENT.md",
        "verify_prompt": "ai-flow/docs/prompts/PROMT_VERIFY.md",
        "inline_memories": False,
        **(cfg.get("context") or {}),
    }
    marker = cfg.get("completion_marker", "<promise>COMPLETE</promise>")
    timeout = int(cfg.get("task_timeout", 1200))
    verify_timeout = int(cfg.get("verify_timeout", 2 * timeout))
    git_cfg = cfg.get("git") or {}

    test_gate = str(cfg.get("test_gate", "feature")).lower()
    if test_gate not in ("feature", "task"):
        print(f"ERROR: test_gate must be 'feature' or 'task', got '{test_gate}' in {args.config}")
        sys.exit(1)
    feature_gate = test_gate == "feature"
    # The green-tests gate follows the requested unit of work: a --task run is one task and runs its
    # own tests; any other run executes whole features, whose tests run once in the verification pass.
    defer_tests = feature_gate and not args.task

    agents = cfg.get("agents") or {}
    agent_name = args.agent or cfg.get("default_agent")
    if agent_name not in agents:
        print(f"ERROR: agent '{agent_name}' not found in {args.config}. "
              f"Available: {', '.join(agents) or '(none)'}")
        sys.exit(1)
    agent = agents[agent_name]
    model = args.model or agent.get("model", "")

    tasks_dir = resolve(ctx["tasks_dir"])
    if not pending_tasks(tasks_dir) and not completed_stems(tasks_dir):
        print(f"No tasks in {ctx['tasks_dir']}. Create a feature folder "
              f"YYYYMMddHHmm_FEATURE with task files (see ai-flow/docs/tasks/README.md).")
        sys.exit(1)

    print(f"Agent: {agent_name}  |  model: {model or '(default)'}  |  test gate: {test_gate}  |  "
          f"root: {REPO_ROOT}")

    def verify_and_archive(feature: str) -> bool:
        ok = run_verification(feature, agent, model, marker, verify_timeout,
                              dry_run=args.dry_run, ctx=ctx)
        if ok and not args.dry_run:
            archive_feature_if_complete(tasks_dir, feature)
            if not commit_verification(feature, git_cfg):
                sys.exit(1)
        if not ok:
            print(f"  [fail] Feature {feature} is not verified — it stays active with its tasks in "
                  f"{DONE_DIR}/; the next feature run retries the verification pass.")
        return ok

    failures = 0
    while True:
        done = completed_stems(tasks_dir)
        pending = pending_tasks(tasks_dir)

        if args.feature:
            pending = [t for t in pending if args.feature.lower() in t.feature.lower()]
        if args.task:
            target = args.task.lower()
            pending = [t for t in pending if target in t.id.lower()]
            if not pending:
                print(f"Task '{args.task}' not found among pending tasks.")
                return

        # Feature gate: a feature whose tasks are all done is verified before any further work.
        unverified = [] if (args.task or not feature_gate) else [
            f for f in unverified_features(tasks_dir)
            if not args.feature or args.feature.lower() in f.lower()
        ]
        if unverified:
            if verify_and_archive(unverified[0]):
                failures = 0
            else:
                failures += 1
                print(f"  [fail] Failure {failures}/3")
                if failures >= 3:
                    print("Stopping after 3 consecutive failures.")
                    sys.exit(1)
            if args.dry_run:
                break
            time.sleep(2)
            continue

        if not pending:
            print("\n[ok] All tasks completed!")
            break

        ready = [t for t in pending if all(_dep_satisfied(d, done) for d in t.deps)]
        if not ready:
            print("\n[!] No tasks ready (unmet dependencies):")
            for t in pending:
                unmet = [d for d in t.deps if not _dep_satisfied(d, done)]
                if unmet:
                    print(f"   {t.feature}/{t.id}: waiting on {unmet}")
            sys.exit(1)

        print(f"\nDone: {len(done)}  |  Pending: {len(pending)}  |  Ready: {[t.id for t in ready]}")

        task = ready[0]
        success = run_agent(task, agent, model, marker, timeout,
                            dry_run=args.dry_run, ctx=ctx, defer_tests=defer_tests)

        if success:
            if not args.dry_run:
                mark_done(task)
                if not feature_gate:
                    archive_feature_if_complete(tasks_dir, task.feature)
                if not commit_task(task, git_cfg):
                    sys.exit(1)
                # A single task that closes its feature still owes the feature gate before archiving
                # (in a feature run the loop picks the feature up as unverified on its next pass).
                if (args.task and feature_gate and task.feature in unverified_features(tasks_dir)
                        and not verify_and_archive(task.feature)):
                    sys.exit(1)
            failures = 0
        else:
            failures += 1
            print(f"  [fail] Failure {failures}/3")
            if failures >= 3:
                print("Stopping after 3 consecutive failures.")
                sys.exit(1)

        if args.dry_run or args.task:
            break
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(1)
