"""Unit coverage for _run_proof_checks status transitions.

Exercises the function directly with a stub proof runner so it does not build a
real agent (which needs optional provider extras). Guards the fix: a proof that
cannot be evaluated must not leave a self-reported "completed" standing as
verified.
"""

from types import SimpleNamespace
from unittest.mock import patch

from agent.consensus.proofs import Observation
from tools.delegate_tool import _run_proof_checks


def _results():
    return [{"task_index": 0, "status": "completed", "summary": "done"}]


def _tasks(proof="pytest -q", expect=0):
    return [{"proof": proof, "proof_expect_exit": expect}]


def test_passing_proof_keeps_completed():
    results = _results()
    with patch(
        "tools.delegate_tool._proof_runner",
        return_value=lambda cmd: Observation(exit_code=0, output_hash="h"),
    ):
        _run_proof_checks(results, _tasks(), SimpleNamespace())
    assert results[0]["status"] == "completed"
    assert results[0]["proof"]["verdict"] == "verified"


def test_failing_proof_is_refuted():
    results = _results()
    with patch(
        "tools.delegate_tool._proof_runner",
        return_value=lambda cmd: Observation(exit_code=1, output_hash="h"),
    ):
        _run_proof_checks(results, _tasks(expect=0), SimpleNamespace())
    assert results[0]["status"] == "refuted"
    assert results[0]["proof"]["verdict"] == "refuted"


def test_crashing_runner_marks_unverified_not_completed():
    """A proof that errors during replay must not read as verified."""

    def _boom(cmd):
        raise RuntimeError("backend down")

    results = _results()
    with patch("tools.delegate_tool._proof_runner", return_value=_boom):
        _run_proof_checks(results, _tasks(), SimpleNamespace())
    assert results[0]["status"] == "unverified"
    assert results[0]["status"] != "completed"
    assert results[0]["proof"]["verdict"] == "unchecked"
    assert "backend down" in results[0]["proof"]["error"]


def test_no_proof_is_left_untouched():
    results = _results()
    with patch("tools.delegate_tool._proof_runner") as runner:
        _run_proof_checks(results, [{}], SimpleNamespace())
    assert results[0]["status"] == "completed"
    assert "proof" not in results[0]
    runner.assert_not_called()


def test_a_child_that_never_completed_is_not_proof_checked():
    results = [{"task_index": 0, "status": "refuted", "summary": "x"}]
    with patch("tools.delegate_tool._proof_runner") as runner:
        _run_proof_checks(results, _tasks(), SimpleNamespace())
    assert results[0]["status"] == "refuted"
    runner.assert_not_called()
