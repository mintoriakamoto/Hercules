"""Tree-of-Thought planning for complex multi-step tasks.

Implements:
- State exploration (multiple solution paths)
- Thought evaluation (rank promising paths)
- Backtracking (explore alternatives)
- Voting (consensus across paths)
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable
import asyncio
from enum import Enum


class ThoughtStatus(Enum):
    """Status of a thought in the tree."""
    EXPLORING = "exploring"
    PROMISING = "promising"
    DEAD_END = "dead_end"
    COMPLETE = "complete"


@dataclass
class Thought:
    """Single node in the thought tree."""
    content: str
    status: ThoughtStatus
    score: float = 0.0
    depth: int = 0
    parent: Optional["Thought"] = None
    children: List["Thought"] = None
    reasoning: str = ""

    def __post_init__(self):
        if self.children is None:
            self.children = []

    def add_child(self, content: str, reasoning: str = "") -> "Thought":
        """Add child thought."""
        child = Thought(
            content=content,
            status=ThoughtStatus.EXPLORING,
            depth=self.depth + 1,
            parent=self,
            reasoning=reasoning,
        )
        self.children.append(child)
        return child


class TreeOfThought:
    """Implements Tree-of-Thought planning."""

    def __init__(
        self,
        initial_state: str,
        evaluator: Callable[[str], float],
        generator: Callable[[str], List[str]],
        max_depth: int = 5,
        beam_width: int = 3,
    ):
        """Initialize ToT planner.

        Args:
            initial_state: Starting problem state
            evaluator: Function to score thoughts (0-1)
            generator: Function to generate next thoughts
            max_depth: Maximum tree depth
            beam_width: Number of best thoughts to explore
        """
        self.root = Thought(content=initial_state, status=ThoughtStatus.EXPLORING)
        self.evaluator = evaluator
        self.generator = generator
        self.max_depth = max_depth
        self.beam_width = beam_width
        self.solutions: List[Thought] = []

    async def explore(self) -> List[str]:
        """Explore thought tree to find solutions."""
        queue = [self.root]

        while queue:
            current = queue.pop(0)

            if current.depth >= self.max_depth:
                if self._is_solution(current):
                    self.solutions.append(current)
                continue

            # Generate child thoughts
            next_thoughts = self.generator(current.content)
            for thought_content in next_thoughts:
                child = current.add_child(thought_content)

                # Evaluate thought
                score = self.evaluator(thought_content)
                child.score = score

                if score > 0.9:
                    child.status = ThoughtStatus.COMPLETE
                    self.solutions.append(child)
                elif score > 0.5:
                    child.status = ThoughtStatus.PROMISING
                    queue.append(child)
                else:
                    child.status = ThoughtStatus.DEAD_END

            # Beam search: keep only top-k
            queue.sort(key=lambda x: x.score, reverse=True)
            queue = queue[:self.beam_width]

        return self._extract_solutions()

    def _is_solution(self, thought: Thought) -> bool:
        """Check if thought is a valid solution."""
        return self.evaluator(thought.content) > 0.8

    def _extract_solutions(self) -> List[str]:
        """Extract paths from root to solutions."""
        paths = []
        for solution in self.solutions:
            path = []
            current = solution
            while current:
                path.insert(0, current.content)
                current = current.parent
            paths.append(" → ".join(path))
        return paths

    def visualize(self) -> str:
        """Get ASCII visualization of thought tree."""
        lines = []

        def draw(node: Thought, prefix: str = ""):
            status_emoji = {
                ThoughtStatus.EXPLORING: "🔍",
                ThoughtStatus.PROMISING: "⭐",
                ThoughtStatus.DEAD_END: "❌",
                ThoughtStatus.COMPLETE: "✓",
            }[node.status]

            score_str = f"({node.score:.2f})" if node.score > 0 else ""
            lines.append(
                f"{prefix}{status_emoji} {node.content[:50]}... {score_str}"
            )

            for i, child in enumerate(node.children):
                is_last = i == len(node.children) - 1
                extension = "└── " if is_last else "├── "
                draw(child, prefix + extension)

        draw(self.root)
        return "\n".join(lines)


__all__ = ["TreeOfThought", "Thought", "ThoughtStatus"]
