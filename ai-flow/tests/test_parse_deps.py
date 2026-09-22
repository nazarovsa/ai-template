"""Unit tests for run_tasks.py: the `Depends on:` / `Parallel with:` parser, parallel batch selection,
the unit-of-work prompts, and feature bookkeeping (NOTES.md, unverified features).

Why a dedicated suite for one parser: it reads text written by people and agents, and every break
costs a derailed queue run. Two real failures it guards against:

* a parenthetical explanation (a format `PROMT_TASKS.md` itself suggests) turned into non-existent
  dependencies — the task was blocked forever;
* a long list wrapped onto the next line lost its tail SILENTLY — the queue did not fail, it ran in
  the wrong order, which is worse than a block.

Run without dependencies beyond PyYAML: `python -m unittest discover -s ai-flow/tests`
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

_RUN_TASKS = Path(__file__).resolve().parents[1] / "run_tasks.py"
_spec = importlib.util.spec_from_file_location("run_tasks", _RUN_TASKS)
_run_tasks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_run_tasks)

parse_deps = _run_tasks._parse_deps
parse_parallel_with = _run_tasks._parse_parallel_with
select_parallel_batch = _run_tasks.select_parallel_batch
Task = _run_tasks.Task

MARKER = "<promise>COMPLETE</promise>"


def _ctx(**extra):
    return {
        "tasks_dir": "ai-flow/docs/tasks",
        "specs_dir": "ai-flow/docs/specs",
        "memories_dir": ".serena/memories",
        "changelog_file": "ai-flow/docs/CHANGELOG.md",
        "agent_prompt": "ai-flow/docs/prompts/PROMT_AGENT.md",
        "verify_prompt": "ai-flow/docs/prompts/PROMT_VERIFY.md",
        "rules_file": "CLAUDE.md",
        "inline_memories": False,
        **extra,
    }


def _scaffold(root: Path, feature: str) -> Path:
    task_dir = root / "ai-flow" / "docs" / "tasks" / feature
    task_dir.mkdir(parents=True)
    (root / ".serena" / "memories").mkdir(parents=True)
    (root / "ai-flow" / "docs" / "specs").mkdir(parents=True)
    (root / "ai-flow" / "docs" / "prompts").mkdir(parents=True)
    (root / "CLAUDE.md").write_text("# Rules\nRULES-BODY\n", encoding="utf-8")
    (root / "ai-flow" / "docs" / "prompts" / "PROMT_AGENT.md").write_text("# Agent\n", encoding="utf-8")
    (root / "ai-flow" / "docs" / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (task_dir / "README.md").write_text("# Feature\n", encoding="utf-8")
    return task_dir


class FeatureBookkeepingTests(unittest.TestCase):
    def test_readme_and_notes_are_not_tasks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_dir = Path(temp_dir)
            feature = tasks_dir / "202601010000_feature"
            feature.mkdir()
            (feature / "README.md").write_text("# Feature\n", encoding="utf-8")
            (feature / "NOTES.md").write_text("# Feature notes\n", encoding="utf-8")
            (feature / "202601010001_run.md").write_text("# Run\n", encoding="utf-8")

            self.assertEqual(
                [task.id for task in _run_tasks.pending_tasks(tasks_dir)], ["202601010001_run"]
            )

    def test_feature_with_every_task_done_is_unverified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_dir = Path(temp_dir)
            closed = tasks_dir / "202601010000_closed"
            open_ = tasks_dir / "202601010010_open"
            (closed / "done").mkdir(parents=True)
            (open_ / "done").mkdir(parents=True)
            (closed / "NOTES.md").write_text("# notes\n", encoding="utf-8")
            (closed / "done" / "202601010001_a.md").write_text("# A\n", encoding="utf-8")
            (open_ / "done" / "202601010011_b.md").write_text("# B\n", encoding="utf-8")
            (open_ / "202601010012_c.md").write_text("# C\n", encoding="utf-8")

            self.assertEqual(_run_tasks.unverified_features(tasks_dir), ["202601010000_closed"])

    def test_recent_changelog_keeps_only_the_last_entries(self):
        changelog = "# Changelog\n\n## one\n- a\n---\n## two\n- b\n---\n## three\n- c\n---\n"
        recent = _run_tasks._recent_changelog(changelog, 2)
        self.assertNotIn("## one", recent)
        self.assertIn("## two", recent)
        self.assertIn("## three", recent)
        self.assertEqual(_run_tasks._recent_changelog(changelog, 0), "")


class PromptTests(unittest.TestCase):
    @staticmethod
    def task(task_id="202601010001_task", feature="202601010000_feature"):
        return Task(id=task_id, feature=feature, title=task_id, content="# Task\n", deps=[],
                    parallel_with=[])

    def build(self, root, **kwargs):
        return _run_tasks.build_prompt(self.task(), _ctx(**kwargs.pop("ctx", {})), MARKER,
                                       repo_root=root, **kwargs)

    def test_feature_unit_defers_tests_and_docs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _scaffold(root, "202601010000_feature")
            prompt = self.build(root, deferred=True)

            self.assertIn("Unit of work: feature", prompt)
            self.assertIn("do NOT run the test suite", prompt)
            self.assertIn("Do NOT edit the changelog", prompt)
            self.assertIn("APPEND this task's entry to the feature notes", prompt)

    def test_task_unit_runs_tests_and_docs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _scaffold(root, "202601010000_feature")
            prompt = self.build(root, deferred=False)

            self.assertIn("Unit of work: task", prompt)
            self.assertIn("build the whole project and run its tests", prompt)
            self.assertIn("APPEND a factual changelog entry", prompt)

    def test_rules_file_is_embedded_unless_the_cli_loads_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _scaffold(root, "202601010000_feature")

            embedded = self.build(root, deferred=True)
            skipped = self.build(root, deferred=True, ctx={"embed_rules": False})

            self.assertIn("RULES-BODY", embedded)
            self.assertNotIn("RULES-BODY", skipped)
            self.assertIn("already loaded `CLAUDE.md`", skipped)

    def test_parallel_worker_leaves_shared_docs_to_integration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _scaffold(root, "202601010000_feature")
            prompt = self.build(root, deferred=True, parallel_worker=True)

            self.assertIn("## Isolated parallel-worker rules", prompt)
            self.assertIn("Instead of appending to `NOTES.md`", prompt)
            self.assertNotIn("APPEND this task's entry to the feature notes", prompt)

    def test_integration_pass_writes_one_note_per_batched_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _scaffold(root, "202601010000_feature")
            prompt = self.build(root, deferred=True, integration=True)

            self.assertIn("PER BATCHED TASK", prompt)
            self.assertNotIn("APPEND this task's entry to the feature notes", prompt)

    def test_integration_task_follows_the_unit_of_work(self):
        task = self.task()
        feature_unit = _run_tasks._integration_task([task], {}, deferred=True, ctx=_ctx())
        task_unit = _run_tasks._integration_task([task], {}, deferred=False, ctx=_ctx())

        self.assertIn("Do NOT run the test suite", feature_unit.content)
        self.assertIn("verification pass records them", feature_unit.content)
        self.assertIn("run its tests", task_unit.content)
        self.assertIn("changelog entry for each completed task", task_unit.content)


class ParseDepsTests(unittest.TestCase):
    def test_plain_reference(self):
        self.assertEqual(parse_deps("- Depends on: 202601010000_a\n"), ["202601010000_a"])

    def test_backticked_reference(self):
        self.assertEqual(parse_deps("- Depends on: `202601010000_a`\n"), ["202601010000_a"])

    def test_comma_separated(self):
        self.assertEqual(
            parse_deps("- Depends on: 202601010000_a, 202601010001_b\n"),
            ["202601010000_a", "202601010001_b"],
        )

    def test_parenthetical_comment_is_not_a_dependency(self):
        """Regression: `waiting on ['(the', 'IsRefundPending', 'field']` — the queue froze."""
        self.assertEqual(
            parse_deps(
                "- Depends on: `202601010000_a` (the `IsRefundPending` field in\n"
                "  `OrderSummaryData` on the backend)\n"
            ),
            ["202601010000_a"],
        )

    def test_wrapped_list_keeps_every_reference(self):
        """Regression: the tail wrapped onto the second line and was lost SILENTLY."""
        self.assertEqual(
            parse_deps(
                "- Depends on: `202601010000_a`, `202601010001_b`,\n"
                "  `202601010002_c`\n"
            ),
            ["202601010000_a", "202601010001_b", "202601010002_c"],
        )

    def test_prompt_template_format_with_trailing_prose(self):
        """The PROMT_TASKS format: `#X (artifact)` — must complete before this task."""
        self.assertEqual(
            parse_deps(
                "- **Depends on:** `#202601010000_a (the DbContext it creates)` "
                "— must complete before this task\n"
            ),
            ["202601010000_a"],
        )

    def test_next_bullet_is_not_swallowed(self):
        self.assertEqual(
            parse_deps("- Depends on: `202601010000_a`\n- Why: needs its aggregate.\n"),
            ["202601010000_a"],
        )

    def test_blank_line_ends_the_continuation(self):
        self.assertEqual(
            parse_deps("- Depends on: `202601010000_a`,\n\n  `202601010001_b`\n"),
            ["202601010000_a"],
        )

    def test_file_name_reference_drops_the_md_suffix(self):
        """Regression: a file name (`…_a.md`) never matched a stem and blocked the feature forever."""
        self.assertEqual(parse_deps("- Depends on: `202601010000_a.md`\n"), ["202601010000_a"])

    def test_file_name_reference_in_a_list_with_a_comment(self):
        self.assertEqual(
            parse_deps(
                "- Depends on: `202601010000_a.md`, `202601010001_b.md` (both change the contract)\n"
            ),
            ["202601010000_a", "202601010001_b"],
        )

    def test_substring_reference_with_dash(self):
        self.assertEqual(parse_deps("- Depends on: terminal-connection\n"), ["terminal-connection"])

    def test_none_variants(self):
        for text in ("none", "нет", "-", "N/A"):
            with self.subTest(text=text):
                self.assertEqual(parse_deps(f"- Depends on: {text}\n"), [])

    def test_russian_heading(self):
        self.assertEqual(parse_deps("- Зависит от: `202601010000_a`\n"), ["202601010000_a"])

    def test_missing_heading(self):
        self.assertEqual(parse_deps("# Task\n\n## Overview\ntext\n"), [])

    def test_blocks_line_is_not_a_dependency(self):
        self.assertEqual(
            parse_deps("- Depends on: none\n- Blocks: `202601010001_b`\n"),
            [],
        )


class ParseParallelWithTests(unittest.TestCase):
    def test_comma_separated_peers(self):
        self.assertEqual(
            parse_parallel_with(
                "- Parallel with: `202601010001_add-api`, `202601010002_add-ui`\n"
            ),
            ["202601010001_add-api", "202601010002_add-ui"],
        )

    def test_none(self):
        self.assertEqual(parse_parallel_with("- Parallel with: none\n"), [])

    def test_russian_heading(self):
        self.assertEqual(
            parse_parallel_with("- Параллельно с: `202601010001_add-api`\n"),
            ["202601010001_add-api"],
        )


class ParallelBatchTests(unittest.TestCase):
    @staticmethod
    def task(task_id, peers=(), deps=()):
        return Task(
            id=task_id, feature="202601010000_feature", title=task_id, content="",
            deps=list(deps), parallel_with=list(peers),
        )

    def test_mutual_ready_tasks_form_batch(self):
        left = self.task("202601010001_add-api", ["add-ui"])
        right = self.task("202601010002_add-ui", ["add-api"])
        self.assertEqual(
            [task.id for task in select_parallel_batch([left, right], [left, right], 2)],
            [left.id, right.id],
        )

    def test_without_declarations_the_first_ready_task_runs_alone(self):
        left = self.task("202601010001_add-api")
        right = self.task("202601010002_add-ui")
        self.assertEqual(select_parallel_batch([left, right], [left, right], 2), [left])

    def test_single_worker_limit_disables_batching(self):
        left = self.task("202601010001_add-api", ["add-ui"])
        right = self.task("202601010002_add-ui", ["add-api"])
        self.assertEqual(select_parallel_batch([left, right], [left, right], 1), [left])

    def test_asymmetric_declaration_is_rejected(self):
        left = self.task("202601010001_add-api", ["add-ui"])
        right = self.task("202601010002_add-ui")
        with self.assertRaisesRegex(ValueError, "must be mutual"):
            select_parallel_batch([left, right], [left, right], 2)

    def test_declared_peer_must_be_ready(self):
        left = self.task("202601010001_add-api", ["add-ui"])
        right = self.task("202601010002_add-ui", ["add-api"], ["foundation-task"])
        with self.assertRaisesRegex(ValueError, "not ready"):
            select_parallel_batch([left], [left, right], 2)

    def test_batch_must_fit_worker_limit(self):
        ids = ["202601010001_a-task", "202601010002_b-task", "202601010003_c-task"]
        tasks = [
            self.task(task_id, [other for other in ids if other != task_id])
            for task_id in ids
        ]
        with self.assertRaisesRegex(ValueError, "needs 3 workers"):
            select_parallel_batch(tasks, tasks, 2)


if __name__ == "__main__":
    unittest.main()
