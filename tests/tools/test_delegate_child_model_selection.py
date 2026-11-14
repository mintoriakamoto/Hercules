"""Child model selection for delegated subagents.

Regression test: task-aware routing emits cloud model names (claude-*, gpt-*),
but a delegated child inherits the parent's base_url. On a local-model
deployment that pairs a cloud name with a local endpoint that cannot serve it,
so the child fails. Routing must be opt-in; by default the child inherits the
parent's model, keeping model and endpoint coherent.
"""

from types import SimpleNamespace
from unittest.mock import patch

from tools.delegate_tool import _select_child_model


def _parent(model="qwen2.5-local"):
    return SimpleNamespace(model=model, base_url="http://localhost:11434/v1")


def test_explicit_model_wins():
    parent = _parent()
    assert (
        _select_child_model("gpt-4o", "do a thing", [], parent, {"enable_task_routing": True})
        == "gpt-4o"
    )


def test_default_inherits_parent_model_not_cloud_route():
    """Routing off by default -> child inherits the parent's (local) model."""
    parent = _parent()
    with patch("tools.delegate_tool.route_task_to_model") as routed:
        result = _select_child_model(None, "complex reasoning task", [], parent, {})
    assert result == "qwen2.5-local"
    routed.assert_not_called()  # the cloud router must not even run by default


def test_opt_in_routing_uses_router():
    parent = _parent()
    decision = SimpleNamespace(
        recommended_tier=SimpleNamespace(value="balanced"),
        confidence=0.9,
        cost_savings_estimate=12.0,
    )
    with patch(
        "tools.delegate_tool.route_task_to_model",
        return_value=("claude-sonnet-5", decision),
    ):
        result = _select_child_model(
            None, "task", [], parent, {"enable_task_routing": True}
        )
    assert result == "claude-sonnet-5"


def test_routing_failure_falls_back_to_parent_model():
    parent = _parent()
    with patch(
        "tools.delegate_tool.route_task_to_model", side_effect=RuntimeError("boom")
    ):
        result = _select_child_model(
            None, "task", [], parent, {"enable_task_routing": True}
        )
    assert result == "qwen2.5-local"
