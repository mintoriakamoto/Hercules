"""Agent algebra: Formal operators for composing agents."""

from enum import Enum
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Dict
from abc import ABC, abstractmethod


class CompositionOp(Enum):
    """Formal composition operators."""
    SEQUENTIAL = "→"  # A then B
    PARALLEL = "||"   # A and B concurrently
    CHOICE = "⊕"      # A or B (failure handling)
    CONDITIONAL = "?"  # if A then B else C
    ITERATION = "*"   # A repeated


@dataclass
class Step:
    """Executable step in a plan."""
    id: str
    name: str
    execute: Callable
    dependencies: List[str]  # IDs of steps this depends on


class Operator(ABC):
    """Base class for composition operators."""

    @abstractmethod
    def apply(self, *agents) -> Callable:
        """Apply operator to agents."""
        pass

    @abstractmethod
    def execution_order(self, *agents) -> List[str]:
        """Get execution order for agents."""
        pass


class Sequential(Operator):
    """Sequential composition: A → B."""

    def apply(self, a: Callable, b: Callable) -> Callable:
        """Execute A, pass result to B."""
        def composed(input_data):
            result_a = a(input_data)
            return b(result_a)
        return composed

    def execution_order(self, *agents) -> List[str]:
        """Sequential: execute in order."""
        return list(range(len(agents)))


class Parallel(Operator):
    """Parallel composition: A || B."""

    def apply(self, *agents) -> Callable:
        """Execute all agents concurrently."""
        import asyncio
        import concurrent.futures

        def composed(input_data):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(agent, input_data) for agent in agents]
                return [f.result() for f in concurrent.futures.as_completed(futures)]

        return composed

    def execution_order(self, *agents) -> List[str]:
        """Parallel: all at once (returned as indices)."""
        return [f"concurrent_{i}" for i in range(len(agents))]


class Choice(Operator):
    """Choice composition: A ⊕ B (try A, fallback to B)."""

    def apply(self, a: Callable, b: Callable) -> Callable:
        """Try A; if fails, try B."""
        def composed(input_data):
            try:
                return a(input_data)
            except Exception:
                return b(input_data)
        return composed

    def execution_order(self, *agents) -> List[str]:
        """Choice: execute first, fallback second if needed."""
        return ["primary", "fallback"]


class Conditional(Operator):
    """Conditional composition: if A then B else C."""

    def apply(self, condition: Callable, on_true: Callable, on_false: Callable) -> Callable:
        """Execute condition, branch to B or C."""
        def composed(input_data):
            if condition(input_data):
                return on_true(input_data)
            else:
                return on_false(input_data)
        return composed

    def execution_order(self, *agents) -> List[str]:
        """Conditional: condition first, then branch."""
        return ["condition", "branch"]


class Iteration(Operator):
    """Iteration composition: A*."""

    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations

    def apply(self, agent: Callable, until: Optional[Callable] = None) -> Callable:
        """Repeat agent until convergence or limit."""
        def composed(input_data):
            current = input_data
            for _ in range(self.max_iterations):
                previous = current
                current = agent(current)

                # Check convergence
                if until and until(current, previous):
                    break

            return current

        return composed

    def execution_order(self, *agents) -> List[str]:
        """Iteration: repeated execution."""
        return [f"iteration_{i}" for i in range(self.max_iterations)]


@dataclass
class Plan:
    """Executable plan as composition expression."""
    steps: Dict[str, Step]
    dependencies: Dict[str, List[str]]

    def validate(self) -> bool:
        """Validate plan is acyclic."""
        # Simple cycle detection using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.dependencies.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in self.steps:
            if node not in visited:
                if has_cycle(node):
                    return False

        return True

    def topological_sort(self) -> List[str]:
        """Get execution order (respects dependencies)."""
        if not self.validate():
            return []

        visited = set()
        order = []

        def visit(node):
            if node in visited:
                return
            visited.add(node)

            for dep in self.dependencies.get(node, []):
                visit(dep)

            order.append(node)

        for node in self.steps:
            visit(node)

        return order


class ExpressionBuilder:
    """Build composition expressions from operators."""

    def __init__(self):
        self.operators = {
            "→": Sequential(),
            "||": Parallel(),
            "⊕": Choice(),
            "?": Conditional(),
            "*": Iteration(),
        }

    def parse(self, expression: str) -> Optional[Callable]:
        """Parse composition expression (simplified)."""
        # This is a basic parser; full implementation would handle
        # operator precedence, associativity, etc.
        if "→" in expression:
            parts = expression.split("→")
            # Compose sequentially
            pass

        return None

    def build_plan(self, steps: Dict[str, Step]) -> Plan:
        """Build executable plan from steps."""
        dependencies = {}
        for step_id, step in steps.items():
            dependencies[step_id] = step.dependencies

        return Plan(steps=steps, dependencies=dependencies)


__all__ = [
    "Sequential",
    "Parallel",
    "Choice",
    "Conditional",
    "Iteration",
    "CompositionOp",
    "Step",
    "Plan",
    "ExpressionBuilder",
]
