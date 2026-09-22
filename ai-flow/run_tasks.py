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
`Depends on:` lines gate ordering. `README.md` (the DesignReview) and `NOTES.md` (the
feature notes) inside a feature folder are not tasks.

Parallel batches (`parallel` in agents.yml, `--max-parallel`) — opt-in per task: ready tasks of ONE
feature that name each other in `Parallel with:` (mutually and completely) run as one atomic batch.
Each worker runs in its own detached git worktree from the same base commit and does not touch shared
docs (rules file, changelog, specs, memories, task Markdown incl. NOTES.md); the successful worker
commits are cherry-picked in task-filename order into an integration worktree, one integration pass
reconciles them and writes the shared docs, and only then is the main branch fast-forwarded. Any
failure leaves the main worktree untouched. Parallel mode requires git auto-commit and a clean main
worktree; `--task` runs are always sequential.

Unit of work (`unit_of_work` in agents.yml; legacy name `test_gate`) — the green-tests gate and the
documentation both apply to the unit of work that was requested:
    feature (default) — a feature run (no --task) tells each task agent to write its tests (TDD) and
        make the solution compile, but NOT to run the tests, and to record what it built only in the
        feature notes (<feature>/NOTES.md, fed to every later task). Once a feature has no pending
        tasks, a verification pass (PROMT_VERIFY.md) builds the solution, runs the whole test suite,
        fixes failures, then records the feature's docs (changelog, spec, as-built, memories) from
        the notes; only a green pass archives the feature. A feature whose tasks are all in done/
        but which is not archived yet is unverified, and is verified first on the next run. A --task
        run is a single-task unit: that task runs its tests and updates the docs itself.
    task — every task builds, runs the tests and updates the docs; features are archived right after
        their last task.

Prompt size: an agent with `loads_claude_md: true` (a CLI that auto-loads the project rules file,
`context.rules_file`, default CLAUDE.md) does not get it embedded again, and only the last
`context.changelog_entries` changelog entries are sent.

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
    python ai-flow/run_tasks.py --max-parallel 4     # explicit parallel batches, up to 4 workers
    python ai-flow/run_tasks.py --dry-run            # show the plan without executing
    python ai-flow/run_tasks.py --config path.yml    # custom config
"""

import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, replace
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
DEFAULT_RULES_FILE = "CLAUDE.md"  # the project rules file (override: context.rules_file)

COMMIT_MAX_LEN = 155  # commit message limit (see the rules file)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: Path) -> dict:
    if not path.exists():
        print(f"ERROR: config not found: {path}")
        sys.exit(1)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve(rel: str, repo_root: Path = REPO_ROOT) -> Path:
    """Resolve a config-relative path against a repository checkout."""
    return (repo_root / rel).resolve()


def display_rel(path: Path, repo_root: Path) -> Path:
    """Path relative to the checkout for prompt text; absolute fallback if unrelated."""
    try:
        return path.relative_to(repo_root)
    except ValueError:
        return path


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
    parallel_with: list[str] = field(default_factory=list)
    file: Path | None = None


# ---------------------------------------------------------------------------
# Task discovery — tasks live in feature folders; completed tasks move to done/
#   ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/<YYYYMMddHHmm_TASK>.md
#   ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/done/<...>.md   (completed task)
#   ai-flow/docs/tasks/done/<YYYYMMddHHmm_FEATURE>/           (fully completed feature)
# ---------------------------------------------------------------------------

DONE_DIR = "done"  # both the per-feature done/ subfolder and the global done/ catalog
NOTES_FILE = "NOTES.md"  # feature notes: each task appends what it built, later tasks read it
NON_TASK_STEMS = {"readme", "notes"}  # feature-folder files that are not tasks


def _is_task_file(path: Path) -> bool:
    return path.stem.lower() not in NON_TASK_STEMS


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


# A task reference is the ASCII slug of a task file name: `202601010000_slug-with-dashes`. Requiring
# a `_` or `-` filters out the ordinary words of an explanation ("must", "complete", "before"), which
# are otherwise indistinguishable from a task name. A substring reference such as
# `terminal-connection` still passes — it has a dash.
_TASK_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*[_-][A-Za-z0-9._-]*$")

_NONE_TOKENS = ("none", "нет", "-", "—", "n/a")


def _parse_refs(content: str, labels: str) -> list[str]:
    """Task references from a labelled metadata line (`Depends on:`, `Parallel with:`).

    The line is written by people and agents, so parsing must survive four things — each of which
    used to break the queue silently:

    1. **Parenthetical explanations.** `PROMT_TASKS.md` itself suggests `#X (what artifact it
       needs)`, and the words of the explanation became non-existent dependencies — the task was
       blocked forever with `waiting on ['(the', 'field']`.
    2. **Backticks.** Task names are written as `` `202601010000_task` ``; without stripping the
       backticks a dependency matched nothing and blocked the queue too.
    3. **Line wraps.** A long dependency list wraps onto the next line, and reading only the first
       line dropped the tail SILENTLY — the task started too early. That is worse than a block: the
       queue does not fail, it runs in the wrong order.
    4. **A `.md` suffix.** Authors refer to a task the way they see it on disk —
       `202601010000_task.md`. Completed tasks are compared by stem (`completed_stems`), so a name
       with the extension matched nothing and blocked the whole feature forever, including tasks
       whose dependency had long been done.
    """
    m = re.search(rf"(?:\*\*)?(?:{labels}):(?:\*\*)?[ \t]*(.*)", content)
    if not m:
        return []

    # Continuations are indented lines that do not start a new list item, heading, or table row.
    # `[1:]` drops the rest of the current line: m.end() sits right before its newline.
    parts = [m.group(1)]
    for line in content[m.end():].split("\n")[1:]:
        if not line.strip() or not line[:1].isspace() or line.lstrip()[:1] in "-*#|>":
            break
        parts.append(line)

    raw = " ".join(parts)
    raw = re.sub(r"\([^()]*\)", " ", raw)   # parenthetical explanations are not references
    raw = raw.replace("`", " ")             # names are formatted as `code`
    # The tail after a dash is a human remark from the PROMT_TASKS format
    # ("`#X (artifact)` — must complete before this task"), not part of the list.
    raw = re.split(r"\s[—–]\s|\s--\s", raw)[0]

    if raw.strip().lower() in _NONE_TOKENS or not raw.strip():
        return []

    refs: list[str] = []
    for tok in re.split(r"[,\s]+", raw):
        tok = tok.strip().lstrip("#").strip(".,;:")
        if tok.lower().endswith(".md"):
            tok = tok[: -len(".md")]     # the author wrote the file name, not the task name
        if not tok or tok.lower() in _NONE_TOKENS:
            continue
        if not _TASK_REF_RE.match(tok):
            continue  # prose, punctuation, a fragment of a parenthesis
        refs.append(tok)
    return refs


def _parse_deps(content: str) -> list[str]:
    """Dependencies from `Depends on:` / `Зависит от:`."""
    return _parse_refs(content, r"Depends on|Зависит от")


def _parse_parallel_with(content: str) -> list[str]:
    """Explicit peers from `Parallel with:` / `Параллельно с:`."""
    return _parse_refs(content, r"Parallel with|Параллельно с")


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
            if not _is_task_file(path):
                continue
            content = path.read_text(encoding="utf-8")
            tasks.append(Task(
                id=path.stem, feature=feat.name,
                title=_first_heading(content) or path.stem,
                content=content, deps=_parse_deps(content),
                parallel_with=_parse_parallel_with(content), file=path,
            ))
    tasks.sort(key=lambda t: (t.feature, t.id))  # timestamp prefixes sort chronologically
    return tasks


def _task_matches_ref(task: Task, ref: str) -> bool:
    ref = ref.lower()
    task_id = task.id.lower()
    return ref == task_id or ref in task_id


def _resolve_parallel_ref(owner: Task, ref: str, pending: list[Task]) -> Task:
    matches = [t for t in pending if t.feature == owner.feature and _task_matches_ref(t, ref)]
    if not matches:
        raise ValueError(f"{owner.id}: parallel peer '{ref}' is not a pending task in {owner.feature}")
    if len(matches) > 1:
        raise ValueError(
            f"{owner.id}: parallel peer '{ref}' is ambiguous: {[t.id for t in matches]}"
        )
    return matches[0]


def select_parallel_batch(ready: list[Task], pending: list[Task], max_workers: int) -> list[Task]:
    """Return the next explicit parallel clique, or the first ready task.

    Parallelism is opt-in and symmetric: every pair in a batch must name each other. Declared peers
    must also be simultaneously ready, otherwise the dependency graph and the parallel declaration
    contradict one another and execution stops instead of silently degrading to sequential order.
    """
    if not ready:
        return []
    first = ready[0]
    if max_workers < 2 or not first.parallel_with:
        return [first]

    resolved = [_resolve_parallel_ref(first, ref, pending) for ref in first.parallel_with]
    peers = sorted({t.id: t for t in resolved}.values(), key=lambda t: t.id)
    if any(t.id == first.id for t in peers):
        raise ValueError(f"{first.id}: a task cannot declare itself as a parallel peer")
    ready_ids = {t.id for t in ready}
    not_ready = [t.id for t in peers if t.id not in ready_ids]
    if not_ready:
        raise ValueError(
            f"{first.id}: declared parallel peers are not ready: {not_ready}; "
            "parallel peers must have compatible dependencies"
        )

    full_group = [first, *peers]
    if len(full_group) > max_workers:
        raise ValueError(
            f"parallel batch {[t.id for t in full_group]} needs {len(full_group)} workers, "
            f"but max_parallel is {max_workers}"
        )
    group_ids = {task.id for task in full_group}
    for member in full_group:
        member_peers = {
            _resolve_parallel_ref(member, ref, pending).id for ref in member.parallel_with
        }
        expected = group_ids - {member.id}
        if member_peers != expected:
            raise ValueError(
                f"parallel declarations must be mutual and complete: {member.id} names "
                f"{sorted(member_peers)}, expected {sorted(expected)}"
            )
    return sorted(full_group, key=lambda t: t.id)


def feature_readme(tasks_dir: Path, feature: str) -> str:
    for name in ("README.md", "readme.md"):
        p = tasks_dir / feature / name
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""


def feature_notes(tasks_dir: Path, feature: str) -> str:
    p = tasks_dir / feature / NOTES_FILE
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def mark_done(task: Task) -> None:
    assert task.file is not None
    dest = task.file.parent / DONE_DIR
    dest.mkdir(exist_ok=True)
    new_path = dest / task.file.name
    task.file.rename(new_path)
    task.file = new_path
    print(f"  -> {task.feature}/{DONE_DIR}/{new_path.name}")


def _has_pending_tasks(feature_dir: Path) -> bool:
    """A feature is still active while any task file remains at its top level (README/NOTES excluded)."""
    return any(_is_task_file(p) for p in feature_dir.glob("*.md"))


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


def _rules_file(ctx: dict) -> str:
    return ctx.get("rules_file") or DEFAULT_RULES_FILE


def _load_rules(ctx: dict, repo_root: Path = REPO_ROOT) -> str:
    name = _rules_file(ctx)
    if not ctx.get("embed_rules", True):
        # The agent CLI auto-loads the rules file (agents.yml `loads_claude_md`) — do not pay twice.
        return (f"## Project Rules ({name})\n\n"
                f"Your CLI has already loaded `{name}` — follow it; it is not repeated here.")
    content = _load_text(repo_root / name)
    return f"## Project Rules ({name})\n\n{content}" if content else ""


def _recent_changelog(changelog: str, entries: int) -> str:
    """The last `entries` `## ` entries of the changelog — the whole journal is not worth resending."""
    if entries <= 0:
        return ""
    blocks: list[list[str]] = []
    for line in changelog.splitlines():
        if line.startswith("## "):
            blocks.append([])
        if blocks:
            blocks[-1].append(line)
    return "\n".join("\n".join(b).strip() for b in blocks[-entries:])


def _load_specs_summary(specs_dir: Path, repo_root: Path = REPO_ROOT) -> str:
    if not specs_dir.exists():
        return ""
    rel = display_rel(specs_dir, repo_root)
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


def _load_memories(memories_dir: Path, *, inline: bool, repo_root: Path = REPO_ROOT) -> str:
    if not memories_dir.exists():
        return ""
    files = sorted(memories_dir.glob("*.md"))
    if not files:
        return ""
    rel = display_rel(memories_dir, repo_root)
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

def _is_git_repo(repo_root: Path = REPO_ROOT) -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo_root, capture_output=True, text=True,
    )
    return r.returncode == 0 and r.stdout.strip() == "true"


def _has_changes(repo_root: Path = REPO_ROOT) -> bool:
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root, capture_output=True, text=True, check=True,
    )
    return bool(r.stdout.strip())


def commit_task(task: Task, git_cfg: dict, repo_root: Path = REPO_ROOT) -> bool:
    template = git_cfg.get("message_template", "feat: task #{id} - {title}")
    return _commit(template.format(id=task.id, title=task.title), f"#{task.id}", git_cfg, repo_root)


def commit_verification(feature: str, git_cfg: dict, repo_root: Path = REPO_ROOT) -> bool:
    template = git_cfg.get("verify_message_template", "test: feature #{feature} - tests green")
    return _commit(template.format(feature=feature), f"feature {feature}", git_cfg, repo_root)


def _commit(message: str, label: str, git_cfg: dict, repo_root: Path = REPO_ROOT) -> bool:
    if not git_cfg.get("enabled", True) or not git_cfg.get("auto_commit", True):
        return True
    if not _is_git_repo(repo_root):
        print("  [!] Not a git repository — skipping commit")
        return True
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    if not _has_changes(repo_root):
        print(f"  [!] Nothing to commit for {label}")
        return True
    # Single line, <= COMMIT_MAX_LEN chars, no tool/AI mentions (see the rules file).
    msg = message.splitlines()[0][:COMMIT_MAX_LEN]
    result = subprocess.run(
        ["git", "commit", "-m", msg], cwd=repo_root, capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"  [ok] {msg}")
        return True
    print(f"  [fail] Commit failed:\n{result.stderr}")
    return False


# ---------------------------------------------------------------------------
# Prompt + agent
# ---------------------------------------------------------------------------

def _ensure_changelog_file(changelog_file: Path, rules_file: str = DEFAULT_RULES_FILE) -> None:
    changelog_file.parent.mkdir(parents=True, exist_ok=True)
    if not changelog_file.exists():
        changelog_file.write_text(
            "# Changelog\n\n"
            "Chronological journal of completed work — each feature verification pass (or a "
            "single-task run) APPENDS an entry below.\n"
            "Reusable patterns are NOT recorded here: they live in Serena memory "
            f"(`.serena/memories/*`) and are indexed in the {rules_file} \"Project knowledge\" table.\n\n"
            "---\n",
            encoding="utf-8",
        )


def _design_block(tasks_dir: Path, feature: str) -> str:
    design = feature_readme(tasks_dir, feature)
    return f"## Feature DesignReview ({feature}/README.md)\n\n{design}" if design else ""


def _notes_rel(ctx: dict, feature: str) -> str:
    return f"{ctx['tasks_dir']}/{feature}/{NOTES_FILE}"


def _notes_block(ctx: dict, feature: str, *, empty: str, repo_root: Path = REPO_ROOT) -> str:
    notes = feature_notes(resolve(ctx["tasks_dir"], repo_root), feature)
    return f"## Feature notes (`{_notes_rel(ctx, feature)}`)\n\n{notes or empty}"


def _shared_docs(ctx: dict) -> str:
    """The coordination files a parallel worker must leave to the batch integration pass."""
    return (f"`{_rules_file(ctx)}`, `{ctx['changelog_file']}`, `{ctx['specs_dir']}/`, "
            f"`{ctx['memories_dir']}/`, and the Markdown under `{ctx['tasks_dir']}/` "
            f"(task files, the DesignReview, `{NOTES_FILE}`)")


def build_prompt(task: Task, ctx: dict, marker: str, *, deferred: bool,
                 repo_root: Path = REPO_ROOT, parallel_worker: bool = False,
                 integration: bool = False) -> str:
    rules_name = _rules_file(ctx)
    agent_prompt = _load_text(resolve(ctx["agent_prompt"], repo_root))
    rules = _load_rules(ctx, repo_root)
    specs = _load_specs_summary(resolve(ctx["specs_dir"], repo_root), repo_root)
    memories = _load_memories(resolve(ctx["memories_dir"], repo_root),
                              inline=ctx.get("inline_memories", False), repo_root=repo_root)
    entries = int(ctx.get("changelog_entries", 3))
    changelog = _recent_changelog(_load_text(resolve(ctx["changelog_file"], repo_root)), entries)
    changelog_block = (
        f"## Changelog (last {entries} entries — the full journal is `{ctx['changelog_file']}`)\n\n"
        f"{changelog or '(No previous entries)'}"
        if entries > 0 else ""
    )
    design_block = _design_block(resolve(ctx["tasks_dir"], repo_root), task.feature)
    notes_block = _notes_block(ctx, task.feature, repo_root=repo_root,
                               empty="(No entries yet — this is the first task of the feature.)")
    notes_rel = _notes_rel(ctx, task.feature)
    notes_line = (
        f"- APPEND one feature-notes entry PER BATCHED TASK to `{notes_rel}` (from the worker reports) —\n"
        f"  not an entry for this integration pass."
        if integration else
        f"- APPEND this task's entry to the feature notes `{notes_rel}`."
    )
    specs_dir = ctx["specs_dir"]

    if deferred:
        unit = ("feature — write this task's tests but do NOT run them, and record what you built only "
                "in the feature notes; the feature verification pass runs the whole suite and writes "
                "the docs after the feature's last task")
        gate_reminder = """- BLOCKING: build the whole solution, test projects included (read_memory("build-and-verify")) — it
  MUST compile. Write every Test Cases row as a real test (TDD) but do NOT run the test suite: the
  feature verification pass runs it once the feature's last task is done. If it does not compile, the
  task is NOT done — do NOT print the completion marker; report the failing command and its output."""
        docs_reminder = f"""{notes_line}
- Do NOT edit the changelog, the feature spec, IMPLEMENTED.md, memories or the {rules_name} table — the
  verification pass records them once for the whole feature, from the notes."""
    else:
        unit = "task — build the solution, run its tests and update the docs before finishing this task"
        gate_reminder = """- BLOCKING: build the whole project and run its tests (read_memory("build-and-verify")). The solution
  MUST compile/build and pass tests. If it does not build, the task is NOT done — do NOT print the
  completion marker; report the failing command and its output instead."""
        docs_reminder = f"""{notes_line}
- Reusable patterns → document them as Serena memory (write_memory) + the {rules_name} table, NOT the changelog.
- APPEND a factual changelog entry (what changed + files) to `{ctx["changelog_file"]}`.
- Update the feature spec (living docs): ensure `{specs_dir}/{task.feature}/README.md` (target) exists
  and record what you built in `{specs_dir}/{task.feature}/IMPLEMENTED.md` (as-built)."""

    parallel_note = ""
    if parallel_worker:
        unit += "; you are an isolated parallel worker (see the rules below the task)"
        parallel_note = f"""
## Isolated parallel-worker rules (override the documentation steps above)

This task is one member of an atomic parallel batch and runs in its own git worktree. Implement its
product code and tests and meet the build gate of the unit of work, but DO NOT edit the shared
coordination files: {_shared_docs(ctx)}. Instead of appending to `{NOTES_FILE}`, END your final
summary with this task's feature-notes entry (the format from the agent instructions): the batch
integration pass writes it, together with any other shared doc. Do not git commit and do not move
the task file.
"""
        docs_reminder = (f"- Parallel worker: do NOT edit {_shared_docs(ctx)} — end your summary with "
                         f"this task's feature-notes entry; the batch integration pass records it.")
    elif integration:
        unit += "; this is the integration pass of a parallel batch"

    return f"""{agent_prompt}

---

{rules}

## Project context

Working directory: {repo_root}
Feature: {task.feature}
Unit of work: {unit}

{specs}

{memories}

{design_block}

{notes_block}

{changelog_block}

---

## Task to implement

{task.content}

{parallel_note}

---

Remember:
- Start from the task's `## Context` map and the feature notes — read the template sections, memories
  and code anchors they name; widen the search only when they are not enough.
- Read existing code before writing.
- Follow project rules ({rules_name}), the Feature DesignReview, and Serena memories.
{gate_reminder}
{docs_reminder}
- DO NOT git commit — the orchestrator handles commits.
- When done, print exactly: {marker}
"""


def build_verify_prompt(feature: str, ctx: dict, marker: str) -> str:
    rules_name = _rules_file(ctx)
    verify_prompt = _load_text(resolve(ctx["verify_prompt"]))
    rules = _load_rules(ctx)
    specs = _load_specs_summary(resolve(ctx["specs_dir"]))
    memories = _load_memories(resolve(ctx["memories_dir"]), inline=ctx.get("inline_memories", False))
    tasks_dir = resolve(ctx["tasks_dir"])
    design_block = _design_block(tasks_dir, feature)
    notes_block = _notes_block(ctx, feature,
                               empty="(No feature notes — reconstruct what was built from the task "
                                     "files and `git log`.)")
    specs_dir = ctx["specs_dir"]
    task_list = "\n".join(
        f"- `{p.relative_to(REPO_ROOT).as_posix()}` — {_first_heading(_load_text(p)) or p.stem}"
        for p in feature_done_tasks(tasks_dir, feature)
    )

    return f"""{verify_prompt}

---

{rules}

## Project context

Working directory: {REPO_ROOT}
Feature: {feature}
Unit of work: feature — this is the verification pass that closes it

{specs}

{memories}

{design_block}

## Tasks of this feature (implemented; tests written but not yet run)

{task_list}

{notes_block}

---

Remember:
- BLOCKING: build the whole solution and run the WHOLE test suite (read_memory("build-and-verify")).
  Fix every failure and re-run until green. Never weaken, skip, or delete a test to get green.
- Every Test Cases row of every task above must exist as a real test — write any that is missing.
- Then record the feature's docs ONCE, from the notes and the final code: APPEND one changelog entry to
  `{ctx["changelog_file"]}`; ensure `{specs_dir}/{feature}/README.md` (target) exists; write
  `{specs_dir}/{feature}/IMPLEMENTED.md` (as-built); add the feature to the index in
  `{specs_dir}/README.md`; record the patterns / domain rules the notes list as Serena memory + the
  {rules_name} table.
- DO NOT git commit and do NOT move task files — the orchestrator archives the feature and commits.
- Print exactly {marker} ONLY when the build and the whole test suite are green and the docs are recorded.
"""


def run_agent(task: Task, agent: dict, model: str, marker: str, timeout: int,
              *, dry_run: bool, ctx: dict, deferred: bool, repo_root: Path = REPO_ROOT,
              parallel_worker: bool = False, integration: bool = False,
              output_sink: list[str] | None = None) -> bool:
    unit = ("feature — tests and docs deferred to the verification pass" if deferred
            else "task — runs its tests and updates the docs")
    if parallel_worker:
        unit += " (parallel worker)"
    elif integration:
        unit += " (parallel batch integration)"
    return _invoke(
        f"  >>  [{task.feature}] {task.id}: {task.title}",
        [f"deps : {task.deps or 'none'}", f"unit : {unit}"],
        lambda: build_prompt(task, ctx, marker, deferred=deferred, repo_root=repo_root,
                             parallel_worker=parallel_worker, integration=integration),
        agent, model, marker, timeout, dry_run=dry_run, ctx=ctx, strict=False,
        repo_root=repo_root, output_sink=output_sink, ensure_changelog=not parallel_worker,
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
            timeout: int, *, dry_run: bool, ctx: dict, strict: bool, repo_root: Path = REPO_ROOT,
            output_sink: list[str] | None = None, ensure_changelog: bool = True) -> bool:
    command = agent["command"].replace("{model}", model)
    print(f"\n{'=' * 72}")
    print(header)
    for line in details:
        print(f"  {line}")
    print(f"  model: {model}")
    print(f"  cmd  : {command}")
    print(f"{'=' * 72}")

    if dry_run:
        print(f"  [dry-run] {command} < <prompt>  (cwd={repo_root})")
        return True

    if ensure_changelog:
        _ensure_changelog_file(resolve(ctx["changelog_file"], repo_root), _rules_file(ctx))
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
            cwd=repo_root, env=env,
        )
        print("  ... agent started, streaming output...", flush=True)

        output_lines: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            output_lines.append(line)

        proc.wait(timeout=timeout)
        output = "".join(output_lines)
        if output_sink is not None:
            output_sink.append(output[-8000:])

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
        if proc and proc.stdout:
            proc.stdout.close()
        os.unlink(tmp.name)


# ---------------------------------------------------------------------------
# Explicit parallel batches — isolated worktrees, atomic integration
# ---------------------------------------------------------------------------

def _git(args: list[str], repo_root: Path, *, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=capture, text=True, check=False,
    )


def _git_head(repo_root: Path) -> str:
    result = _git(["rev-parse", "HEAD"], repo_root)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "cannot resolve Git HEAD")
    return result.stdout.strip()


def _changed_paths(repo_root: Path) -> list[str]:
    result = _git(["status", "--porcelain"], repo_root)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "cannot inspect worktree changes")
    paths = []
    for line in result.stdout.splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def _parallel_worker_shared_changes(repo_root: Path, ctx: dict) -> list[str]:
    exact = {"CLAUDE.md", "AGENTS.md", _rules_file(ctx), ctx["changelog_file"]}
    prefixes = (
        f"{ctx['specs_dir'].rstrip('/')}/",
        f"{ctx['memories_dir'].rstrip('/')}/",
        f"{ctx['tasks_dir'].rstrip('/')}/",
    )
    return [
        path for path in _changed_paths(repo_root)
        if path in exact or any(path.startswith(prefix) for prefix in prefixes)
    ]


def _worktree_task(task: Task, worktree_root: Path) -> Task:
    assert task.file is not None
    relative_file = task.file.relative_to(REPO_ROOT)
    return replace(task, file=worktree_root / relative_file)


def _integration_task(batch: list[Task], worker_reports: dict[str, str], *, deferred: bool,
                      ctx: dict) -> Task:
    task_details = "\n\n---\n\n".join(task.content for task in batch)
    reports = "\n\n".join(
        f"### {task.id}\n\n{worker_reports.get(task.id) or '(no worker report)'}"
        for task in batch
    )
    ids = ", ".join(task.id for task in batch)
    notes_rel = _notes_rel(ctx, batch[0].feature)
    if deferred:
        docs_change = (
            f"2. Do NOT write the changelog, the feature spec, IMPLEMENTED.md or memories — under the "
            f"feature unit of work the feature verification pass records them once, from `{notes_rel}`."
        )
        gate_change = (
            "4. Build the whole combined solution, test projects included — it MUST compile. Do NOT run "
            "the test suite: the feature verification pass runs it after the feature's last task."
        )
        gate_acceptance = "3. The combined solution builds/compiles (tests run in the verification pass)."
    else:
        docs_change = (
            f"2. Append a factual changelog entry for each completed task ({ids}), update the feature "
            f"target/as-built specs and any required Serena memories + the {_rules_file(ctx)} table."
        )
        gate_change = ("4. Build the combined solution and run its tests; fix every failure in the "
                       "combined tree.")
        gate_acceptance = "3. The combined solution builds and its tests pass."
    return Task(
        id=f"parallel-batch-{batch[0].id}", feature=batch[0].feature,
        title=f"Integrate parallel batch: {', '.join(task.title for task in batch)}",
        content=f"""# Integrate parallel task batch

## Overview
The product-code commits for this parallel batch are already combined in this checkout.
Do not reimplement the tasks. Inspect the combined diff and reconcile only what is needed for the
batch to be complete as one coherent change.

## Changes
1. APPEND one feature-notes entry per batched task ({ids}) to `{notes_rel}`, taken from the worker
   reports below (correct it where the combined code differs). Do not add an entry for this
   integration pass itself.
{docs_change}
3. Resolve integration issues between the task implementations if any are discovered.
{gate_change}

## Batched task texts

{task_details}

## Worker reports

{reports}

## Acceptance Criteria
1. [ ] Every batched task's acceptance criteria remain satisfied in the combined tree.
2. [ ] The feature notes (and, under the task unit of work, the shared docs) cover the whole batch.
{gate_acceptance}
""",
    )


def run_parallel_batch(batch: list[Task], agent: dict, model: str, marker: str, timeout: int,
                       *, dry_run: bool, ctx: dict, git_cfg: dict, deferred: bool,
                       archive: bool) -> bool:
    """Run an explicit parallel batch atomically: workers → deterministic integration → fast-forward.

    `archive` — archive the feature once the batch closes it (the task unit of work). Under the feature
    unit of work the feature stays active: the verification pass archives it.
    """
    ids = [task.id for task in batch]
    print(f"\n[parallel] Atomic batch: {ids}")
    if dry_run:
        for task in batch:
            run_agent(task, agent, model, marker, timeout, dry_run=True, ctx=ctx,
                      deferred=deferred, parallel_worker=True)
        print("  [dry-run] workers -> deterministic integration -> atomic fast-forward")
        return True

    if not git_cfg.get("enabled", True) or not git_cfg.get("auto_commit", True):
        print("  [fail] Parallel batches require git.enabled=true and git.auto_commit=true")
        return False
    if not _is_git_repo(REPO_ROOT):
        print("  [fail] Parallel batches require a Git repository")
        return False
    if _has_changes(REPO_ROOT):
        print("  [fail] Parallel batches require a clean main worktree")
        return False

    batch_dir = Path(tempfile.mkdtemp(prefix="ai-flow-parallel-")).resolve()
    worktrees: list[Path] = []
    try:
        worker_roots: dict[str, Path] = {}
        for index, task in enumerate(batch):
            root = batch_dir / f"worker-{index + 1}-{task.id}"
            result = _git(["worktree", "add", "--detach", str(root), "HEAD"], REPO_ROOT)
            if result.returncode != 0:
                print(f"  [fail] Cannot create worktree for {task.id}: {result.stderr.strip()}")
                return False
            worktrees.append(root)
            worker_roots[task.id] = root

        def execute(task: Task) -> tuple[str, bool, str, str]:
            root = worker_roots[task.id]
            worker_task = _worktree_task(task, root)
            output: list[str] = []
            success = run_agent(
                worker_task, agent, model, marker, timeout, dry_run=False, ctx=ctx,
                deferred=deferred, repo_root=root, parallel_worker=True, output_sink=output,
            )
            if not success:
                return task.id, False, "", "".join(output)
            shared_changes = _parallel_worker_shared_changes(root, ctx)
            if shared_changes:
                print(
                    f"  [fail] {task.id} changed integration-owned files: {shared_changes}"
                )
                return task.id, False, "", "".join(output)
            mark_done(worker_task)
            if not commit_task(worker_task, git_cfg, root):
                return task.id, False, "", "".join(output)
            return task.id, True, _git_head(root), "".join(output)

        results: dict[str, tuple[bool, str, str]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as pool:
            futures = {pool.submit(execute, task): task for task in batch}
            for future in concurrent.futures.as_completed(futures):
                task = futures[future]
                try:
                    task_id, success, commit, report = future.result()
                except Exception as exc:
                    print(f"  [fail] Parallel worker {task.id} crashed: {exc}")
                    task_id, success, commit, report = task.id, False, "", ""
                results[task_id] = (success, commit, report)

        failed = [task.id for task in batch if not results.get(task.id, (False, ""))[0]]
        if failed:
            print(f"  [fail] Parallel workers failed: {failed}; main worktree was not changed")
            return False

        integration_root = batch_dir / "integration"
        result = _git(["worktree", "add", "--detach", str(integration_root), "HEAD"], REPO_ROOT)
        if result.returncode != 0:
            print(f"  [fail] Cannot create integration worktree: {result.stderr.strip()}")
            return False
        worktrees.append(integration_root)

        for task in sorted(batch, key=lambda item: item.id):
            commit = results[task.id][1]
            result = _git(["cherry-pick", commit], integration_root)
            if result.returncode != 0:
                print(
                    f"  [fail] Parallel tasks overlap while integrating {task.id}:\n"
                    f"{result.stdout}{result.stderr}"
                )
                return False

        worker_reports = {
            task.id: results[task.id][2].replace(marker, "[worker completion marker]")
            for task in batch
        }
        integration_task = _integration_task(batch, worker_reports, deferred=deferred, ctx=ctx)
        if not run_agent(
            integration_task, agent, model, marker, timeout, dry_run=False, ctx=ctx,
            deferred=deferred, repo_root=integration_root, integration=True,
        ):
            print("  [fail] Batch integration pass failed; main worktree was not changed")
            return False

        if archive:
            archive_feature_if_complete(resolve(ctx["tasks_dir"], integration_root), batch[0].feature)
        if not commit_task(integration_task, git_cfg, integration_root):
            return False
        integrated_head = _git_head(integration_root)

        if _has_changes(REPO_ROOT):
            recovery_branch = f"ai-flow/recover-{batch[0].id}"
            _git(["branch", "-f", recovery_branch, integrated_head], REPO_ROOT)
            print(
                "  [fail] Main worktree changed while the batch was running; refusing to integrate. "
                f"Completed batch is preserved as {recovery_branch} ({integrated_head})."
            )
            return False
        result = _git(["merge", "--ff-only", integrated_head], REPO_ROOT)
        if result.returncode != 0:
            recovery_branch = f"ai-flow/recover-{batch[0].id}"
            _git(["branch", "-f", recovery_branch, integrated_head], REPO_ROOT)
            print(
                f"  [fail] Atomic fast-forward failed; batch preserved as {recovery_branch}:\n"
                f"{result.stdout}{result.stderr}"
            )
            return False
        print(f"  [ok] Parallel batch integrated atomically at {integrated_head[:12]}")
        return True
    finally:
        for root in reversed(worktrees):
            _git(["worktree", "remove", "--force", str(root)], REPO_ROOT)
        shutil.rmtree(batch_dir, ignore_errors=True)


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
    parser.add_argument(
        "--max-parallel", type=int,
        help="maximum workers for explicit parallel batches (0 or 1 disables parallel execution)",
    )
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
        "rules_file": DEFAULT_RULES_FILE,
        "inline_memories": False,
        **(cfg.get("context") or {}),
    }
    marker = cfg.get("completion_marker", "<promise>COMPLETE</promise>")
    timeout = int(cfg.get("task_timeout", 1200))
    verify_timeout = int(cfg.get("verify_timeout", 2 * timeout))
    git_cfg = cfg.get("git") or {}
    parallel_cfg = cfg.get("parallel") or {}
    configured_parallel = int(parallel_cfg.get("max_workers", 2))
    max_parallel = args.max_parallel if args.max_parallel is not None else configured_parallel
    if max_parallel < 0:
        parser.error("--max-parallel must be zero or greater")
    if not parallel_cfg.get("enabled", True) or args.task:
        max_parallel = 1

    unit_of_work = str(cfg.get("unit_of_work", cfg.get("test_gate", "feature"))).lower()
    if unit_of_work not in ("feature", "task"):
        print(f"ERROR: unit_of_work must be 'feature' or 'task', got '{unit_of_work}' in {args.config}")
        sys.exit(1)
    feature_mode = unit_of_work == "feature"
    # Tests and docs follow the requested unit of work: a --task run is one task and does both itself;
    # any other run executes whole features, which get both once, in the verification pass.
    deferred = feature_mode and not args.task

    agents = cfg.get("agents") or {}
    agent_name = args.agent or cfg.get("default_agent")
    if agent_name not in agents:
        print(f"ERROR: agent '{agent_name}' not found in {args.config}. "
              f"Available: {', '.join(agents) or '(none)'}")
        sys.exit(1)
    agent = agents[agent_name]
    model = args.model or agent.get("model", "")
    ctx["embed_rules"] = not agent.get("loads_claude_md", False)

    tasks_dir = resolve(ctx["tasks_dir"])
    if not pending_tasks(tasks_dir) and not completed_stems(tasks_dir):
        print(f"No tasks in {ctx['tasks_dir']}. Create a feature folder "
              f"YYYYMMddHHmm_FEATURE with task files (see ai-flow/docs/tasks/README.md).")
        sys.exit(1)

    print(f"Agent: {agent_name}  |  model: {model or '(default)'}  |  unit of work: {unit_of_work}  |  "
          f"max parallel: {max_parallel}  |  root: {REPO_ROOT}")

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

        # Feature mode: a feature whose tasks are all done is verified before any further work.
        unverified = [] if (args.task or not feature_mode) else [
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

        try:
            batch = select_parallel_batch(ready, pending, max_parallel)
        except ValueError as exc:
            print(f"\n[!] Invalid parallel declaration: {exc}")
            sys.exit(1)

        task = batch[0]
        if len(batch) > 1:
            # The batch commits and archives itself atomically (see run_parallel_batch).
            success = run_parallel_batch(batch, agent, model, marker, timeout,
                                         dry_run=args.dry_run, ctx=ctx, git_cfg=git_cfg,
                                         deferred=deferred, archive=not feature_mode)
        else:
            success = run_agent(task, agent, model, marker, timeout,
                                dry_run=args.dry_run, ctx=ctx, deferred=deferred)
            if success and not args.dry_run:
                mark_done(task)
                if not feature_mode:
                    archive_feature_if_complete(tasks_dir, task.feature)
                if not commit_task(task, git_cfg):
                    sys.exit(1)
                # A single task that closes its feature still owes the feature pass before archiving
                # (in a feature run the loop picks the feature up as unverified on its next pass).
                if (args.task and feature_mode and task.feature in unverified_features(tasks_dir)
                        and not verify_and_archive(task.feature)):
                    sys.exit(1)

        if success:
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
