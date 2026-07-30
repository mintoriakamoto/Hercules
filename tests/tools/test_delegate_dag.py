"""Tests for delegate_task's dependency-DAG scheduling (per-task depends_on).

A task may declare ``depends_on=[indices]`` to run only after those tasks
complete, receiving their summaries as input. Without any depends_on the batch
runs flat and in parallel exactly as before, so these tests also pin the
no-op default and the validation guards (range, self-dependency, cycles).
"""

import json
import threading
import unittest
from unittest.mock import MagicMock, patch

from tools.delegate_tool import (
    delegate_task,
    _parse_dependencies,
    _run_dag_batch,
)


def _make_mock_parent():
    parent = MagicMock()
    parent.base_url = "https://openrouter.ai/api/v1"
    parent.api_key = "***"
    parent.provider = "openrouter"
    parent.api_mode = "chat_completions"
    parent.model = "anthropic/claude-sonnet-4"
    parent.platform = "cli"
    parent.providers_allowed = None
    parent.providers_ignored = None
    parent.providers_order = None
    parent.provider_sort = None
    parent._session_db = None
    parent._delegate_depth = 0
    parent._active_children = []
    parent._active_children_lock = threading.Lock()
    parent._print_fn = None
    parent.tool_progress_callback = None
    parent.thinking_callback = None
    parent._interrupt_requested = False
    parent._delegate_spinner = None
    return parent


class TestParseDependencies(unittest.TestCase):
    def test_no_deps_all_empty(self):
        deps, err = _parse_dependencies([{"goal": "a"}, {"goal": "b"}])
        self.assertIsNone(err)
        self.assertEqual(deps, {0: set(), 1: set()})

    def test_valid_chain(self):
        deps, err = _parse_dependencies(
            [{"goal": "a"}, {"goal": "b", "depends_on": [0]}, {"goal": "c", "depends_on": [0, 1]}]
        )
        self.assertIsNone(err)
        self.assertEqual(deps, {0: set(), 1: {0}, 2: {0, 1}})

    def test_out_of_range_rejected(self):
        deps, err = _parse_dependencies([{"goal": "a", "depends_on": [5]}])
        self.assertIsNone(deps)
        self.assertIn("out-of-range", err)

    def test_self_dependency_rejected(self):
        deps, err = _parse_dependencies([{"goal": "a", "depends_on": [0]}])
        self.assertIsNone(deps)
        self.assertIn("itself", err)

    def test_cycle_rejected(self):
        deps, err = _parse_dependencies(
            [{"goal": "a", "depends_on": [1]}, {"goal": "b", "depends_on": [0]}]
        )
        self.assertIsNone(deps)
        self.assertIn("cycle", err)

    def test_non_integer_rejected(self):
        deps, err = _parse_dependencies([{"goal": "a"}, {"goal": "b", "depends_on": ["x"]}])
        self.assertIsNone(deps)
        self.assertIn("non-integer", err)

    def test_non_list_rejected(self):
        deps, err = _parse_dependencies([{"goal": "a"}, {"goal": "b", "depends_on": 0}])
        self.assertIsNone(deps)
        self.assertIn("must be a list", err)


@patch("tools.delegate_tool._build_child_agent", return_value=MagicMock())
class TestDagExecution(unittest.TestCase):
    def test_dependency_ordering_enforced(self, _build):
        """A dependent task must not start until its prerequisite finished."""
        order = []
        order_lock = threading.Lock()

        def fake_run(task_index=0, goal="", child=None, parent_agent=None, **kw):
            with order_lock:
                order.append(("start", task_index))
            # Task 0 is the producer; give it a beat so a broken scheduler that
            # ignores deps would let task 1 start first.
            import time as _t
            if task_index == 0:
                _t.sleep(0.15)
            with order_lock:
                order.append(("end", task_index))
            return {"task_index": task_index, "status": "completed",
                    "summary": f"out{task_index}", "duration_seconds": 0}

        with patch("tools.delegate_tool._run_single_child", side_effect=fake_run):
            parent = _make_mock_parent()
            result = json.loads(
                delegate_task(
                    tasks=[{"goal": "producer"}, {"goal": "consumer", "depends_on": [0]}],
                    parent_agent=parent,
                )
            )
        # Producer must fully finish before the consumer starts.
        self.assertEqual(order[0], ("start", 0))
        end0 = order.index(("end", 0))
        start1 = order.index(("start", 1))
        self.assertLess(end0, start1, f"consumer started before producer finished: {order}")
        # Both tasks reported, in input order.
        statuses = [(e["task_index"], e["status"]) for e in result["results"]]
        self.assertEqual(statuses, [(0, "completed"), (1, "completed")])

    def test_prerequisite_output_injected_into_dependent_goal(self, _build):
        """The consumer's goal must carry the producer's summary."""
        seen_goals = {}

        def fake_run(task_index=0, goal="", child=None, parent_agent=None, **kw):
            seen_goals[task_index] = goal
            return {"task_index": task_index, "status": "completed",
                    "summary": f"PRODUCED-BY-{task_index}", "duration_seconds": 0}

        with patch("tools.delegate_tool._run_single_child", side_effect=fake_run):
            parent = _make_mock_parent()
            delegate_task(
                tasks=[{"goal": "make data"}, {"goal": "summarize it", "depends_on": [0]}],
                parent_agent=parent,
            )
        # Producer goal is untouched; consumer goal embeds producer output.
        self.assertNotIn("PRODUCED-BY-0", seen_goals[0])
        self.assertIn("summarize it", seen_goals[1])
        self.assertIn("PRODUCED-BY-0", seen_goals[1])
        self.assertIn("prerequisite", seen_goals[1].lower())

    def test_diamond_dependency_runs_all_four(self, _build):
        """0 → {1,2} → 3 : every task runs exactly once, 3 last."""
        order = []
        lock = threading.Lock()

        def fake_run(task_index=0, goal="", child=None, parent_agent=None, **kw):
            with lock:
                order.append(task_index)
            return {"task_index": task_index, "status": "completed",
                    "summary": f"o{task_index}", "duration_seconds": 0}

        with patch("tools.delegate_tool._run_single_child", side_effect=fake_run):
            parent = _make_mock_parent()
            result = json.loads(
                delegate_task(
                    tasks=[
                        {"goal": "root"},
                        {"goal": "left", "depends_on": [0]},
                        {"goal": "right", "depends_on": [0]},
                        {"goal": "merge", "depends_on": [1, 2]},
                    ],
                    parent_agent=parent,
                )
            )
        self.assertEqual(sorted(order), [0, 1, 2, 3])
        self.assertEqual(order[0], 0)          # root first
        self.assertEqual(order[-1], 3)         # merge last
        self.assertEqual(len(result["results"]), 4)

    def test_cycle_returns_error_without_spawning(self, _build):
        with patch("tools.delegate_tool._run_single_child") as mock_run:
            parent = _make_mock_parent()
            result = json.loads(
                delegate_task(
                    tasks=[
                        {"goal": "a", "depends_on": [1]},
                        {"goal": "b", "depends_on": [0]},
                    ],
                    parent_agent=parent,
                )
            )
        self.assertIn("error", result)
        self.assertIn("cycle", result["error"])
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
