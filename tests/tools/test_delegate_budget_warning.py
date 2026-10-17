"""A subagent under delegation.child_timeout_seconds is warned once at 80% of
its budget through its steer channel; the total timeout is unchanged."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

import pytest

from tools.delegate_tool import _await_child_with_budget_warning


class _Child:
    def __init__(self):
        self.steers = []

    def steer(self, text):
        self.steers.append((time.monotonic(), text))
        return True


def _run(fn):
    pool = ThreadPoolExecutor(max_workers=1)
    return pool, pool.submit(fn)


def test_warns_once_then_returns_when_child_finishes_after_warning():
    child = _Child()
    release = threading.Event()
    pool, fut = _run(lambda: (release.wait(5), "done")[1])

    def _release_after_warning():
        while not child.steers:
            time.sleep(0.01)
        release.set()

    threading.Thread(target=_release_after_warning, daemon=True).start()
    start = time.monotonic()
    assert _await_child_with_budget_warning(fut, child, 1.0) == "done"
    assert len(child.steers) == 1
    warned_at, text = child.steers[0]
    assert 0.7 <= warned_at - start <= 1.0
    assert "[delegation budget warning]" in text
    pool.shutdown(wait=False)


def test_still_times_out_at_full_budget():
    child = _Child()
    stop = threading.Event()
    pool, fut = _run(lambda: stop.wait(5))
    start = time.monotonic()
    with pytest.raises(FuturesTimeoutError):
        _await_child_with_budget_warning(fut, child, 0.5)
    elapsed = time.monotonic() - start
    assert 0.45 <= elapsed < 0.9
    assert len(child.steers) == 1
    stop.set()
    pool.shutdown(wait=False)


def test_fast_child_is_never_warned():
    child = _Child()
    pool, fut = _run(lambda: "quick")
    assert _await_child_with_budget_warning(fut, child, 2.0) == "quick"
    assert child.steers == []
    pool.shutdown(wait=False)


def test_no_timeout_configured_waits_without_warning():
    child = _Child()
    pool, fut = _run(lambda: (time.sleep(0.05), "ok")[1])
    assert _await_child_with_budget_warning(fut, child, None) == "ok"
    assert child.steers == []
    pool.shutdown(wait=False)


def test_child_without_steer_is_tolerated():
    stop = threading.Event()
    pool, fut = _run(lambda: stop.wait(5))
    with pytest.raises(FuturesTimeoutError):
        _await_child_with_budget_warning(fut, object(), 0.3)
    stop.set()
    pool.shutdown(wait=False)
