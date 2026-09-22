"""Integration tests for isolated, atomic parallel task execution (real git, fake agent)."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


_RUN_TASKS = Path(__file__).resolve().parents[1] / "run_tasks.py"
_spec = importlib.util.spec_from_file_location("run_tasks_parallel", _RUN_TASKS)
_run_tasks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_run_tasks)

FEATURE = "202601010000_parallel-feature"

# Workers write product files only; the integration pass writes the feature notes and, under the task
# unit of work, the changelog. A worker that touched a shared doc would fail the batch.
FAKE_AGENT = """from pathlib import Path
import sys

prompt = sys.stdin.read()
root = Path.cwd()
tasks = root / "ai-flow" / "docs" / "tasks" / "%s"
if "## Isolated parallel-worker rules" in prompt:
    name = "task-a" if "# task-a" in prompt else "task-b"
    (root / f"{name}.txt").write_text(name, encoding="utf-8")
    print(f"## {name} - built {name}.txt")
else:
    notes = tasks / "NOTES.md"
    notes.write_text("# Feature notes\\n## task-a\\n## task-b\\n", encoding="utf-8")
    if "Unit of work: task" in prompt:
        changelog = root / "ai-flow" / "docs" / "CHANGELOG.md"
        changelog.write_text(changelog.read_text(encoding="utf-8") + "integrated\\n", encoding="utf-8")
print("<promise>COMPLETE</promise>")
""" % FEATURE


class ParallelExecutionTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        root = self.root
        self.task_dir = root / "ai-flow" / "docs" / "tasks" / FEATURE
        self.task_dir.mkdir(parents=True)
        (root / ".serena" / "memories").mkdir(parents=True)
        (root / "ai-flow" / "docs" / "specs").mkdir(parents=True)
        (root / "ai-flow" / "docs" / "prompts").mkdir(parents=True)
        (root / "CLAUDE.md").write_text("# Rules\n", encoding="utf-8")
        (root / "ai-flow" / "docs" / "prompts" / "PROMT_AGENT.md").write_text(
            "# Agent\n", encoding="utf-8"
        )
        (root / "ai-flow" / "docs" / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
        (self.task_dir / "README.md").write_text("# Parallel feature\n", encoding="utf-8")
        self.left_path = self.task_dir / "202601010001_task-a.md"
        self.right_path = self.task_dir / "202601010002_task-b.md"
        self.left_path.write_text(
            "# task-a\n- Depends on: none\n- Parallel with: 202601010002_task-b\n", encoding="utf-8",
        )
        self.right_path.write_text(
            "# task-b\n- Depends on: none\n- Parallel with: 202601010001_task-a\n", encoding="utf-8",
        )
        (root / "fake_agent.py").write_text(FAKE_AGENT, encoding="utf-8")
        for args in (
            ["init"],
            ["config", "user.email", "test@example.com"],
            ["config", "user.name", "Test User"],
            ["add", "-A"],
            ["commit", "-m", "initial"],
        ):
            subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    def tearDown(self):
        self._temp.cleanup()

    def run_batch(self, *, deferred: bool, archive: bool) -> bool:
        original_root = _run_tasks.REPO_ROOT
        _run_tasks.REPO_ROOT = self.root
        try:
            tasks = _run_tasks.pending_tasks(self.root / "ai-flow" / "docs" / "tasks")
            return _run_tasks.run_parallel_batch(
                tasks,
                {"command": "python fake_agent.py", "model": ""},
                "", "<promise>COMPLETE</promise>", 60,
                dry_run=False,
                ctx={
                    "tasks_dir": "ai-flow/docs/tasks",
                    "specs_dir": "ai-flow/docs/specs",
                    "memories_dir": ".serena/memories",
                    "changelog_file": "ai-flow/docs/CHANGELOG.md",
                    "agent_prompt": "ai-flow/docs/prompts/PROMT_AGENT.md",
                    "rules_file": "CLAUDE.md",
                    "inline_memories": False,
                },
                git_cfg={
                    "enabled": True,
                    "auto_commit": True,
                    "message_template": "feat: {id} - {title}",
                },
                deferred=deferred, archive=archive,
            )
        finally:
            _run_tasks.REPO_ROOT = original_root

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def test_feature_unit_batch_keeps_the_feature_for_the_verification_pass(self):
        self.assertTrue(self.run_batch(deferred=True, archive=False))

        self.assertEqual(self.read("task-a.txt"), "task-a")
        self.assertEqual(self.read("task-b.txt"), "task-b")
        self.assertTrue((self.task_dir / "done" / self.left_path.name).exists())
        self.assertTrue((self.task_dir / "done" / self.right_path.name).exists())
        self.assertIn("## task-a", (self.task_dir / "NOTES.md").read_text(encoding="utf-8"))
        self.assertNotIn("integrated", self.read("ai-flow/docs/CHANGELOG.md"))
        tasks_dir = self.root / "ai-flow" / "docs" / "tasks"
        self.assertEqual(_run_tasks.unverified_features(tasks_dir), [FEATURE])

    def test_task_unit_batch_writes_docs_and_archives_the_feature(self):
        self.assertTrue(self.run_batch(deferred=False, archive=True))

        self.assertIn("integrated", self.read("ai-flow/docs/CHANGELOG.md"))
        archived = self.root / "ai-flow" / "docs" / "tasks" / "done" / FEATURE
        self.assertTrue((archived / "done" / self.left_path.name).exists())
        self.assertTrue((archived / "NOTES.md").exists())
        self.assertFalse(self.task_dir.exists())

    def test_worker_touching_a_shared_doc_fails_the_batch_without_changing_main(self):
        agent = self.root / "fake_agent.py"
        agent.write_text(agent.read_text(encoding="utf-8").replace(
            'print(f"## {name} - built {name}.txt")',
            'print(f"## {name}"); (tasks / "NOTES.md").write_text("worker", encoding="utf-8")',
        ), encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "shared-doc agent"], cwd=self.root, check=True,
                       capture_output=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, check=True,
                              capture_output=True, text=True).stdout

        self.assertFalse(self.run_batch(deferred=True, archive=False))

        self.assertEqual(subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, check=True,
                                        capture_output=True, text=True).stdout, head)
        self.assertTrue(self.left_path.exists())
        self.assertFalse((self.root / "task-a.txt").exists())


if __name__ == "__main__":
    unittest.main()
