"""Tests for delegate_task's self-correcting repair loop.

When ``delegation.verify_repair_rounds > 0``, a task the adversarial verifier
REFUTES is handed to a repair child seeded with the refutation, then
re-verified — looping until the verdict flips to verified or the round budget
is spent. At the default (0 rounds) the verify wave stays purely advisory, so
these tests also pin that the feature is inert unless turned on.
"""

import json
import threading
import unittest
from unittest.mock import MagicMock, patch

from tools.delegate_tool import delegate_task


def _make_mock_parent(depth=0):
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
    parent._delegate_depth = depth
    parent._active_children = []
    parent._active_children_lock = threading.Lock()
    parent._print_fn = None
    parent.tool_progress_callback = None
    parent.thinking_callback = None
    parent._interrupt_requested = False
    return parent


def _primary(idx=0, summary="Wrote /tmp/out.txt with 3 rows"):
    return {
        "task_index": idx,
        "status": "completed",
        "summary": summary,
        "api_calls": 3,
        "duration_seconds": 5.0,
    }


def _child(summary, status="completed", cost=0.01):
    return {
        "task_index": 0,
        "status": status,
        "summary": summary,
        "api_calls": 2,
        "duration_seconds": 2.0,
        "_child_cost_usd": cost,
    }


@patch("tools.delegate_tool._build_child_agent", return_value=MagicMock())
class TestRepairLoop(unittest.TestCase):
    @patch("tools.delegate_tool._get_verify_repair_rounds", return_value=0)
    @patch("tools.delegate_tool._run_single_child")
    def test_disabled_by_default_no_repair(self, mock_run, _rounds, _build):
        """rounds=0: a refuted task is NOT repaired; no extra children spawn."""
        mock_run.side_effect = [
            _primary(),
            _child("VERDICT: refuted — /tmp/out.txt does not exist"),
        ]
        parent = _make_mock_parent()
        result = json.loads(
            delegate_task(goal="do thing", verify=True, parent_agent=parent)
        )
        entry = result["results"][0]
        self.assertEqual(mock_run.call_count, 2)  # primary + verifier only
        self.assertTrue(entry["verification"]["verdict"].startswith("VERDICT: refuted"))
        self.assertNotIn("repairs", entry)

    @patch("tools.delegate_tool._get_verify_repair_rounds", return_value=2)
    @patch("tools.delegate_tool._run_single_child")
    def test_refuted_task_repaired_then_verified(self, mock_run, _rounds, _build):
        """A refuted task is repaired and, once re-verified, adopts the fix."""
        mock_run.side_effect = [
            _primary(),                                            # primary work
            _child("VERDICT: refuted — /tmp/out.txt does not exist"),  # verify
            _child("Created /tmp/out.txt with 3 rows; confirmed via wc -l => 3"),  # repair
            _child("VERDICT: verified\nRead /tmp/out.txt: 3 rows present."),       # re-verify
        ]
        parent = _make_mock_parent()
        result = json.loads(
            delegate_task(goal="do thing", verify=True, parent_agent=parent)
        )
        entry = result["results"][0]
        self.assertEqual(mock_run.call_count, 4)  # primary+verify+repair+reverify
        # Verdict flipped to verified.
        self.assertEqual(entry["verification"]["verdict"], "VERDICT: verified")
        # The repaired outcome replaced the original refuted claim.
        self.assertIn("confirmed via wc -l", entry["summary"])
        self.assertIn("VERDICT: verified", entry["summary"])
        # Repair trail recorded.
        self.assertEqual(len(entry["repairs"]), 1)
        self.assertEqual(entry["repairs"][0]["outcome"], "reverified")
        self.assertEqual(entry["repairs"][0]["verdict"], "VERDICT: verified")
        # No internal scratch keys leaked to the parent.
        self.assertNotIn("_verify_base_summary", entry)
        self.assertNotIn("_repair_candidate", entry)

    @patch("tools.delegate_tool._get_verify_repair_rounds", return_value=2)
    @patch("tools.delegate_tool._run_single_child")
    def test_still_refuted_after_all_rounds(self, mock_run, _rounds, _build):
        """If repair never satisfies the verifier, the final verdict is refuted
        and every round is recorded — the loop is bounded by the round budget."""
        mock_run.side_effect = [
            _primary(),
            _child("VERDICT: refuted — missing file"),          # verify
            _child("Attempted fix A"),                          # repair r1
            _child("VERDICT: refuted — still missing"),         # re-verify r1
            _child("Attempted fix B"),                          # repair r2
            _child("VERDICT: refuted — still missing"),         # re-verify r2
        ]
        parent = _make_mock_parent()
        result = json.loads(
            delegate_task(goal="do thing", verify=True, parent_agent=parent)
        )
        entry = result["results"][0]
        self.assertEqual(mock_run.call_count, 6)  # 2 rounds * (repair+reverify) + primary + verify
        self.assertTrue(entry["verification"]["verdict"].startswith("VERDICT: refuted"))
        self.assertEqual(len(entry["repairs"]), 2)

    @patch("tools.delegate_tool._get_verify_repair_rounds", return_value=3)
    @patch("tools.delegate_tool._run_single_child")
    def test_repair_that_fails_stops_the_loop(self, mock_run, _rounds, _build):
        """A repair child that produces no real outcome halts the loop (no
        pointless re-verify), and the failure is recorded."""
        mock_run.side_effect = [
            _primary(),
            _child("VERDICT: refuted — nope"),                  # verify
            _child(None, status="failed"),                      # repair fails
        ]
        parent = _make_mock_parent()
        result = json.loads(
            delegate_task(goal="do thing", verify=True, parent_agent=parent)
        )
        entry = result["results"][0]
        self.assertEqual(mock_run.call_count, 3)  # no re-verify happened
        self.assertTrue(entry["verification"]["verdict"].startswith("VERDICT: refuted"))
        self.assertEqual(entry["repairs"][0]["outcome"], "repair_failed")

    @patch("tools.delegate_tool._get_verify_repair_rounds", return_value=2)
    @patch("tools.delegate_tool._run_single_child")
    def test_verified_task_never_enters_repair(self, mock_run, _rounds, _build):
        """A task the verifier accepts is left completely alone."""
        mock_run.side_effect = [
            _primary(),
            _child("VERDICT: verified\nchecked."),
        ]
        parent = _make_mock_parent()
        result = json.loads(
            delegate_task(goal="do thing", verify=True, parent_agent=parent)
        )
        entry = result["results"][0]
        self.assertEqual(mock_run.call_count, 2)  # no repair/reverify
        self.assertEqual(entry["verification"]["verdict"], "VERDICT: verified")
        self.assertNotIn("repairs", entry)


class TestRepairHelpers(unittest.TestCase):
    def test_verdict_is_refuted(self):
        from tools.delegate_tool import _verdict_is_refuted

        self.assertTrue(_verdict_is_refuted("VERDICT: refuted — x"))
        self.assertTrue(_verdict_is_refuted("  verdict: REFUTED — y"))
        self.assertFalse(_verdict_is_refuted("VERDICT: verified"))
        self.assertFalse(_verdict_is_refuted("VERDICT: unverifiable — z"))
        self.assertFalse(_verdict_is_refuted(""))

    def test_repair_goal_embeds_all_three_parts(self):
        from tools.delegate_tool import _build_repair_goal

        g = _build_repair_goal("build docs", "docs at site/", "site/ is empty")
        self.assertIn("build docs", g)
        self.assertIn("docs at site/", g)
        self.assertIn("site/ is empty", g)
        self.assertIn("REFUTED", g)

    def test_repair_rounds_clamped(self):
        from tools.delegate_tool import _get_verify_repair_rounds, _VERIFY_REPAIR_MAX_ROUNDS

        with patch("tools.delegate_tool._load_config", return_value={"verify_repair_rounds": 99}):
            self.assertEqual(_get_verify_repair_rounds(), _VERIFY_REPAIR_MAX_ROUNDS)
        with patch("tools.delegate_tool._load_config", return_value={"verify_repair_rounds": -5}):
            self.assertEqual(_get_verify_repair_rounds(), 0)
        with patch("tools.delegate_tool._load_config", return_value={"verify_repair_rounds": "bad"}):
            self.assertEqual(_get_verify_repair_rounds(), 0)
        with patch("tools.delegate_tool._load_config", return_value={}):
            self.assertEqual(_get_verify_repair_rounds(), 0)


if __name__ == "__main__":
    unittest.main()
