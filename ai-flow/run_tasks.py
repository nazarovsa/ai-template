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

Agents are configured in `ai-flow/agents.yml` (claude / codex / zcode). The prompt
is always piped via stdin. The completion marker (default <promise>COMPLETE</promise>)
and per-task timeout come from the config.

Usage:
    python ai-flow/run_tasks.py                      # default agent from agents.yml
    python ai-flow/run_tasks.py --agent codex        # override agent
    python ai-flow/run_tasks.py --agent zcode --model glm-4.6
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
    if not git_cfg.get("enabled", True) or not git_cfg.get("auto_commit", True):
        return True
    if not _is_git_repo():
        print("  [!] Not a git repository — skipping commit")
        return True
    subprocess.run(["git", "add", "-A"], cwd=REPO_ROOT, check=True)
    if not _has_changes():
        print(f"  [!] Nothing to commit for #{task.id}")
        return True
    template = git_cfg.get("message_template", "feat: task #{id} - {title}")
    # Single line, <= COMMIT_MAX_LEN chars, no tool/AI mentions (see CLAUDE.md).
    msg = template.format(id=task.id, title=task.title).splitlines()[0][:COMMIT_MAX_LEN]
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


def build_prompt(task: Task, ctx: dict, marker: str) -> str:
    agent_prompt = _load_text(resolve(ctx["agent_prompt"]))
    claude_md = _load_claude_md()
    specs = _load_specs_summary(resolve(ctx["specs_dir"]))
    memories = _load_memories(resolve(ctx["memories_dir"]), inline=ctx.get("inline_memories", False))
    changelog = _load_text(resolve(ctx["changelog_file"]))
    design = feature_readme(resolve(ctx["tasks_dir"]), task.feature)
    specs_dir = ctx["specs_dir"]

    design_block = (
        f"## Feature DesignReview ({task.feature}/README.md)\n\n{design}"
        if design else ""
    )

    return f"""{agent_prompt}

---

{claude_md}

## Project context

Working directory: {REPO_ROOT}
Feature: {task.feature}

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
- BLOCKING: build the whole project and run its tests (read_memory("build-and-verify")). The solution
  MUST compile/build and pass tests. If it does not build, the task is NOT done — do NOT print the
  completion marker; report the failing command and its output instead.
- Reusable patterns → document them as Serena memory (write_memory) + the CLAUDE.md table, NOT the changelog.
- APPEND a factual changelog entry (what changed + files) to `{ctx["changelog_file"]}`.
- Update the feature spec (living docs): ensure `{specs_dir}/{task.feature}/README.md` (target) exists
  and record what you built in `{specs_dir}/{task.feature}/IMPLEMENTED.md` (as-built).
- DO NOT git commit — the orchestrator handles commits.
- When done, print exactly: {marker}
"""


def run_agent(task: Task, agent: dict, model: str, marker: str, timeout: int,
              *, dry_run: bool, ctx: dict) -> bool:
    command = agent["command"].replace("{model}", model)
    print(f"\n{'=' * 72}")
    print(f"  >>  [{task.feature}] {task.id}: {task.title}")
    print(f"  deps : {task.deps or 'none'}")
    print(f"  model: {model}")
    print(f"  cmd  : {command}")
    print(f"{'=' * 72}")

    if dry_run:
        print(f"  [dry-run] {command} < <prompt>  (cwd={REPO_ROOT})")
        return True

    _ensure_changelog_file(resolve(ctx["changelog_file"]))
    prompt = build_prompt(task, ctx, marker)

    env = os.environ.copy()
    for k, v in (agent.get("env") or {}).items():
        env[k] = os.path.expandvars(str(v))

    tmp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False)
    proc = None
    try:
        tmp.write(prompt)
        tmp.close()

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
        "inline_memories": False,
        **(cfg.get("context") or {}),
    }
    marker = cfg.get("completion_marker", "<promise>COMPLETE</promise>")
    timeout = int(cfg.get("task_timeout", 1200))
    git_cfg = cfg.get("git") or {}

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

    print(f"Agent: {agent_name}  |  model: {model or '(default)'}  |  root: {REPO_ROOT}")

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
        success = run_agent(task, agent, model, marker, timeout, dry_run=args.dry_run, ctx=ctx)

        if success:
            if not args.dry_run:
                mark_done(task)
                archive_feature_if_complete(tasks_dir, task.feature)
                if not commit_task(task, git_cfg):
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
