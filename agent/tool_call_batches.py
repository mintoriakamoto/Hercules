"""Normalize local bridge batches before persistence and per-tool execution."""

from copy import deepcopy
import hashlib
import json
from typing import Any, Optional

from agent.transports.types import ToolCall
from tools.tool_search import TOOL_CALL_NAME, BRIDGE_TOOL_NAMES

MAX_CALLS_PER_DISPATCH = 10


def _is_connector_name(name: str) -> bool:
    """No connector dispatch layer in Hercules — always False."""
    try:
        from tools.connectors import is_connector_name
        return is_connector_name(name)
    except Exception:
        return False


def _coalesce_id(tc: Any) -> str:
    """Effective call id of a ToolCall (object or dict)."""
    for attr in ("call_id", "id"):
        value = getattr(tc, attr, None) if not isinstance(tc, dict) else tc.get(attr)
        if isinstance(value, str) and value.strip():
            return value.split("|", 1)[0].strip() or value
    return ""


def _deterministic_id(fn_name: str, arguments: str, index: int = 0) -> str:
    """Deterministic call_id when none is provided (avoids breaking prefix caching with random ids)."""
    seed = f"{fn_name}:{arguments}:{index}"
    return f"call_{hashlib.sha256(seed.encode('utf-8', errors='replace')).hexdigest()[:12]}"


def _uniquify_ids(tool_calls: list) -> None:
    """Ensure every tool call in one turn has a unique id."""
    seen: set[str] = set()
    for tc in tool_calls:
        cid = _coalesce_id(tc)
        if not cid:
            continue
        if cid in seen:
            new_id = f"{cid}_d{sum(1 for s in seen if s.startswith(cid))}"
            if hasattr(tc, "id"):
                tc.id = new_id
            elif isinstance(tc, dict):
                tc["id"] = new_id
        seen.add(_coalesce_id(tc))


def _normalize_entries(args: dict[str, Any]) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Normalize ``tool_call`` arguments into a ``calls[]`` list of entries.

    Accepts the batch shape ``{"calls": [{"name", "arguments"}, ...]}``
    and the legacy single shape ``{"name": ..., "arguments": ...}``.
    Each entry's ``arguments`` is coerced to a dict. Returns ``(entries, None)``
    or ``([], error_message)``.
    """
    raw_calls = args.get("calls")
    if raw_calls is None:
        if not str(args.get("name") or "").strip():
            return [], "tool_call requires 'calls' (an array of {name, arguments})"
        raw_calls = [{"name": args.get("name"), "arguments": args.get("arguments")}]
    if isinstance(raw_calls, str):
        try:
            raw_calls = json.loads(raw_calls)
        except json.JSONDecodeError as e:
            return [], f"tool_call 'calls' is not valid JSON: {e}"
    if isinstance(raw_calls, dict):
        raw_calls = [raw_calls]
    if not isinstance(raw_calls, list) or not raw_calls:
        return [], "tool_call 'calls' must be a non-empty array of {name, arguments}"
    entries: list[dict[str, Any]] = []
    for position, raw in enumerate(raw_calls):
        if not isinstance(raw, dict):
            return [], f"tool_call calls[{position}] must be an object with 'name' and 'arguments'"
        name = str(raw.get("name") or "").strip()
        if not name:
            return [], f"tool_call calls[{position}] requires a 'name'"
        if name in BRIDGE_TOOL_NAMES:
            return [], f"tool_call cannot invoke '{name}' (it is itself a bridge tool)"
        raw_args = raw.get("arguments")
        if raw_args is None or (isinstance(raw_args, str) and not raw_args.strip()):
            raw_args = {}
        elif isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args)
            except json.JSONDecodeError:
                raw_args = {}
        if not isinstance(raw_args, dict):
            raw_args = {}
        entries.append({"name": name, "arguments": raw_args})
    return entries, None


def expand_local_tool_batches(tool_calls: list, *, provider_data: dict | None = None) -> list:
    """Give every local entry the ordinary agent execution and persistence path.

    Registry-only batch dispatch loses the live agent's inline tools, guardrails,
    and per-server concurrency policy. Split the *new* assistant turn instead,
    before it is persisted; never rewrite an earlier conversation message.
    Connector-only batches keep their existing dispatcher and wire shape.
    """
    expanded, replacements = [], {}
    for call in tool_calls:
        if call.name != TOOL_CALL_NAME:
            expanded.append(call)
            continue
        try:
            args = call.arguments
            entries, error = _normalize_entries(json.loads(args) if isinstance(args, str) else (args or {}))
        except (TypeError, ValueError, AttributeError):
            entries, error = [], True
        if (error or not 1 < len(entries) <= MAX_CALLS_PER_DISPATCH
                or all(_is_connector_name(entry["name"]) for entry in entries)):
            expanded.append(call)
            continue
        parent_id = _coalesce_id(call)
        children = []
        for index, entry in enumerate(entries):
            arguments = json.dumps({"calls": [entry]}, ensure_ascii=False)
            if index == 0:
                child = deepcopy(call)
                child.arguments = arguments
            else:
                child = ToolCall(
                    id=_deterministic_id(TOOL_CALL_NAME, parent_id + arguments, index),
                    name=TOOL_CALL_NAME,
                    arguments=arguments,
                )
            expanded.append(child)
            children.append(child)
        replacements[parent_id] = children
    _uniquify_ids(expanded)
    # Native providers replay ordered blocks instead of rebuilding them from
    # tool_calls. Replace the matching tool block in place, preserving signed
    # thinking/text blocks and their order exactly.
    if provider_data and replacements:
        for key, replace in (("anthropic_content_blocks", _anthropic_children),
                             ("bedrock_content_blocks", _bedrock_children)):
            if blocks := provider_data.get(key):
                provider_data[key] = [child for block in blocks for child in replace(block, replacements)]
    return expanded


def _anthropic_children(block, replacements):
    children = replacements.get(block.get("id")) if block.get("type") == "tool_use" else None
    if children is None:
        return [block]
    return [{**block, "id": _coalesce_id(child),
             "input": json.loads(child.arguments)} for child in children]


def _bedrock_children(block, replacements):
    tool = block.get("toolUse")
    children = replacements.get(tool.get("toolUseId")) if isinstance(tool, dict) else None
    if children is None:
        return [block]
    return [{**block, "toolUse": {**tool, "toolUseId": _coalesce_id(child),
                                  "input": json.loads(child.arguments)}} for child in children]
