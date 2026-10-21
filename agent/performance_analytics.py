"""Performance analytics and optimization tracking.

Tracks:
- Latency profiling
- Cost per operation
- Token efficiency
- Success rates
- Model performance comparison
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import json


@dataclass
class PerformanceMetric:
    """Single performance measurement."""
    operation: str
    latency_ms: float
    tokens_used: int
    cost_usd: float
    success: bool
    model: str
    timestamp: datetime = field(default_factory=datetime.now)


class PerformanceTracker:
    """Track and analyze performance metrics."""

    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.model_rates = {
            "claude-opus": {"input": 0.015, "output": 0.045},
            "claude-sonnet": {"input": 0.003, "output": 0.015},
            "claude-haiku": {"input": 0.00025, "output": 0.00125},
        }

    def record_operation(
        self,
        operation: str,
        latency_ms: float,
        tokens_used: int,
        model: str,
        success: bool = True,
    ):
        """Record operation performance."""
        cost = self._calculate_cost(tokens_used, model)
        metric = PerformanceMetric(
            operation=operation,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            cost_usd=cost,
            success=success,
            model=model,
        )
        self.metrics.append(metric)

    def _calculate_cost(self, tokens: int, model: str) -> float:
        """Calculate operation cost in USD."""
        rates = self.model_rates.get(model, {"input": 0.01, "output": 0.03})
        # Assume 60/40 input/output split
        input_tokens = tokens * 0.6
        output_tokens = tokens * 0.4
        return (
            input_tokens * rates["input"] / 1000000 +
            output_tokens * rates["output"] / 1000000
        )

    def get_operation_stats(self, operation: str) -> Dict:
        """Get statistics for an operation."""
        ops = [m for m in self.metrics if m.operation == operation]
        if not ops:
            return {}

        latencies = [m.latency_ms for m in ops]
        costs = [m.cost_usd for m in ops]
        success_count = sum(1 for m in ops if m.success)

        return {
            "count": len(ops),
            "avg_latency_ms": sum(latencies) / len(latencies),
            "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)],
            "max_latency_ms": max(latencies),
            "total_cost_usd": sum(costs),
            "avg_cost_per_op": sum(costs) / len(ops),
            "success_rate": success_count / len(ops),
        }

    def get_model_comparison(self) -> Dict:
        """Compare models by performance."""
        models = {}
        for metric in self.metrics:
            if metric.model not in models:
                models[metric.model] = []
            models[metric.model].append(metric)

        comparison = {}
        for model, metrics in models.items():
            latencies = [m.latency_ms for m in metrics]
            costs = [m.cost_usd for m in metrics]
            comparison[model] = {
                "avg_latency_ms": sum(latencies) / len(latencies),
                "total_cost_usd": sum(costs),
                "operations": len(metrics),
            }

        return comparison

    def recommend_model(self, operation: str) -> str:
        """Recommend best model for operation."""
        # For simple operations, use Haiku
        if operation in ["classify", "analyze", "format"]:
            return "claude-haiku"

        # For complex tasks, use Sonnet
        if operation in ["generate", "plan", "debug"]:
            return "claude-sonnet"

        # Default to Sonnet for safety
        return "claude-sonnet"

    def export_metrics(self, filepath: str):
        """Export metrics to JSON file."""
        data = {
            "metrics": [
                {
                    "operation": m.operation,
                    "latency_ms": m.latency_ms,
                    "tokens": m.tokens_used,
                    "cost_usd": m.cost_usd,
                    "success": m.success,
                    "model": m.model,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in self.metrics
            ],
            "summary": {
                "total_operations": len(self.metrics),
                "total_cost_usd": sum(m.cost_usd for m in self.metrics),
                "success_rate": (
                    sum(1 for m in self.metrics if m.success) / len(self.metrics)
                    if self.metrics else 0
                ),
            },
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)


__all__ = ["PerformanceTracker", "PerformanceMetric"]
