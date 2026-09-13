#!/usr/bin/env python3
"""
Process-based parallel delegation executor.

Replaces thread-based concurrency (ThreadPoolExecutor) with process-based
parallelism (ProcessPoolExecutor) for true parallelism without GIL constraints.
Each subagent runs in its own process with isolated Python interpreter.

Benefits:
  - True parallelism on multi-core systems (no GIL)
  - Better isolation between subagents
  - Cleaner resource cleanup on exit
  - Scalable to many concurrent subagents

Trade-offs:
  - Higher IPC overhead than threads
  - Serialization cost for task definitions and results
  - Process startup latency (~100ms per process)
  - Memory overhead per process

Provides drop-in replacement for ThreadPoolExecutor in delegate_task:
  - ProcessDelegationExecutor wraps ProcessPoolExecutor
  - Same submit() and map() interface
  - Automatic serialization of task objects
  - Result deserialization and error propagation
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import pickle
import traceback
from concurrent.futures import (
    ProcessPoolExecutor,
    Future,
    TimeoutError as FuturesTimeoutError,
    as_completed,
)
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Context for passing through process boundary
try:
    _mp_context = mp.get_context("spawn")  # spawn safer than fork, works on Windows
except ValueError:
    # Fallback on systems where spawn is not available
    _mp_context = None


class ProcessDelegationExecutor:
    """Wrapper around ProcessPoolExecutor for subagent delegation.

    Handles serialization/deserialization of task objects and results,
    providing the same interface as ThreadPoolExecutor for drop-in replacement.
    """

    def __init__(self, max_workers: Optional[int] = None):
        """Initialize process pool executor.

        Args:
            max_workers: Maximum number of worker processes.
                        Defaults to CPU count.
        """
        kwargs = {"max_workers": max_workers}
        if _mp_context is not None:
            kwargs["mp_context"] = _mp_context
        self._executor = ProcessPoolExecutor(**kwargs)
        self._futures: Dict[Future, str] = {}  # Future -> delegation_id mapping

    def submit(
        self,
        func: Callable,
        task_index: int,
        goal: str,
        child: Dict[str, Any],
        parent_agent: Any,
    ) -> Future:
        """Submit a subagent task to the process pool.

        Args:
            func: Worker function (_run_single_child)
            task_index: Index in the task batch
            goal: The delegation goal
            child: Child agent configuration dict
            parent_agent: Parent agent instance

        Returns:
            Future representing the running task
        """
        # Serialize task arguments for IPC
        try:
            task_args = {
                "task_index": task_index,
                "goal": goal,
                "child": child,
                "parent_agent_state": self._serialize_agent_state(parent_agent),
            }
            # Test serializability before submitting
            _ = pickle.dumps(task_args)
        except Exception as e:
            logger.error(f"Failed to serialize task {task_index}: {e}")
            # Return a failed future
            fut: Future = Future()
            fut.set_exception(
                RuntimeError(f"Task serialization failed: {e}")
            )
            return fut

        # Submit to process pool
        future = self._executor.submit(
            _process_delegation_worker,
            func,
            task_args,
        )
        self._futures[future] = f"task_{task_index}"
        return future

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor and wait for all processes to finish."""
        self._executor.shutdown(wait=wait)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown(wait=True)

    @staticmethod
    def _serialize_agent_state(agent: Any) -> Dict[str, Any]:
        """Extract serializable state from agent for IPC.

        Does NOT serialize the agent object itself (contains non-serializable
        objects like event loops, file handles, MCP connections). Instead
        extracts the relevant configuration and state needed by the child.
        """
        if agent is None:
            return {}

        try:
            return {
                "session_id": getattr(agent, "session_id", ""),
                "model": getattr(agent, "model", "claude-opus-4"),
                "max_iterations": getattr(agent, "max_iterations", 20),
                "enabled_toolsets": getattr(agent, "enabled_toolsets", None),
                "disabled_toolsets": getattr(agent, "disabled_toolsets", None),
            }
        except Exception as e:
            logger.warning(f"Failed to serialize agent state: {e}")
            return {}


def _process_delegation_worker(
    func: Callable,
    serialized_args: Dict[str, Any],
) -> Dict[str, Any]:
    """Worker function running in subprocess.

    Deserializes task arguments, calls the actual worker function,
    and handles serialization of results.

    Args:
        func: The actual worker function (_run_single_child)
        serialized_args: Serialized task arguments

    Returns:
        Result dict or error dict
    """
    try:
        task_index = serialized_args["task_index"]
        goal = serialized_args["goal"]
        child = serialized_args["child"]
        parent_agent_state = serialized_args["parent_agent_state"]

        # Call the actual worker function in this process
        # Note: parent_agent is None in subprocess; child doesn't need it
        result = func(
            task_index=task_index,
            goal=goal,
            child=child,
            parent_agent=None,  # Parent agent unavailable in subprocess
        )

        # Ensure result is serializable
        _ = pickle.dumps(result)
        return result

    except Exception as e:
        # Capture exception with full traceback for debugging
        return {
            "task_index": serialized_args.get("task_index"),
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


class ProcessPoolDelegationCoordinator:
    """High-level coordinator for managing process-based delegation batches.

    Handles:
    - Process pool lifecycle management
    - Task ordering and synchronization
    - Result collection and error handling
    - Progress tracking across multiple processes
    """

    def __init__(self, max_workers: Optional[int] = None):
        """Initialize coordinator.

        Args:
            max_workers: Maximum concurrent processes
        """
        self.executor = ProcessDelegationExecutor(max_workers=max_workers)
        self.active_tasks: Dict[Future, Dict[str, Any]] = {}

    def submit_batch(
        self,
        tasks: List[Dict[str, Any]],
        runner_func: Callable,
        parent_agent: Any,
    ) -> List[Future]:
        """Submit a batch of tasks for parallel execution.

        Args:
            tasks: List of task dicts with 'task_index', 'goal', 'child'
            runner_func: The worker function (_run_single_child)
            parent_agent: Parent agent instance

        Returns:
            List of Future objects
        """
        futures = []
        for task in tasks:
            future = self.executor.submit(
                runner_func,
                task_index=task["task_index"],
                goal=task["goal"],
                child=task["child"],
                parent_agent=parent_agent,
            )
            self.active_tasks[future] = task
            futures.append(future)
        return futures

    def wait_for_batch(
        self,
        futures: List[Future],
        timeout: Optional[float] = None,
    ) -> tuple[List[Dict], List[Exception]]:
        """Wait for all tasks to complete and collect results.

        Args:
            futures: List of futures from submit_batch
            timeout: Maximum time to wait

        Returns:
            Tuple of (results_list, exceptions_list)
        """
        results = []
        exceptions = []

        try:
            for future in as_completed(futures, timeout=timeout):
                try:
                    result = future.result(timeout=1)
                    results.append(result)
                except Exception as e:
                    exceptions.append(e)
                finally:
                    self.active_tasks.pop(future, None)
        except FuturesTimeoutError:
            exceptions.append(FuturesTimeoutError("Batch execution timeout"))

        return results, exceptions

    def shutdown(self):
        """Shutdown executor and cleanup resources."""
        self.executor.shutdown(wait=True)
        self.active_tasks.clear()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown()


# Module-level coordinator (optional singleton pattern)
_coordinator: Optional[ProcessPoolDelegationCoordinator] = None


def get_coordinator(max_workers: Optional[int] = None) -> ProcessPoolDelegationCoordinator:
    """Get or create module-level coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = ProcessPoolDelegationCoordinator(max_workers=max_workers)
    return _coordinator
