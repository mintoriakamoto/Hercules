"""Helpers for translating OpenAI-style tool schemas to Gemini's schema subset."""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

# Gemini's ``FunctionDeclaration.parameters`` field accepts the ``Schema``
# object, which is only a subset of OpenAPI 3.0 / JSON Schema.  Strip fields
# outside that subset before sending Hercules tool schemas to Google.
_GEMINI_SCHEMA_ALLOWED_KEYS = {
    "type",
    "format",
    "title",
    "description",
    "nullable",
    "enum",
    "maxItems",
    "minItems",
    "properties",
    "required",
    "minProperties",
    "maxProperties",
    "minLength",
    "maxLength",
    "pattern",
    "example",
    "anyOf",
    "propertyOrdering",
    "default",
    "items",
    "minimum",
    "maximum",
}


def sanitize_gemini_schema(schema: Any) -> Dict[str, Any]:
    """Return a Gemini-compatible copy of a tool parameter schema.

    Hercules tool schemas are OpenAI-flavored JSON Schema and may contain keys
    such as ``$schema`` or ``additionalProperties`` that Google's Gemini
    ``Schema`` object rejects.  This helper preserves the documented Gemini
    subset and recursively sanitizes nested ``properties`` / ``items`` /
    ``anyOf`` definitions.
    """

    if not isinstance(schema, dict):
        return {}

    cleaned: Dict[str, Any] = {}
    for key, value in schema.items():
        if key not in _GEMINI_SCHEMA_ALLOWED_KEYS:
            continue
        if key == "properties":
            if not isinstance(value, dict):
                continue
            props: Dict[str, Any] = {}
            for prop_name, prop_schema in value.items():
                if not isinstance(prop_name, str):
                    continue
                props[prop_name] = sanitize_gemini_schema(prop_schema)
            cleaned[key] = props
            continue
        if key == "items":
            cleaned[key] = sanitize_gemini_schema(value)
            continue
        if key == "anyOf":
            if not isinstance(value, list):
                continue
            cleaned[key] = [
                sanitize_gemini_schema(item) for item in value if isinstance(item, dict)
            ]
            continue
        cleaned[key] = value

    # Gemini's Schema validator requires every ``enum`` entry to be a string,
    # even when the parent ``type`` is ``integer`` / ``number`` / ``boolean``.
    # OpenAI / OpenRouter / Anthropic accept typed enums (e.g. Discord's
    # ``auto_archive_duration: {type: integer, enum: [60, 1440, 4320, 10080]}``),
    # so we only drop the ``enum`` when it would collide with Gemini's rule.
    # Keeping ``type: integer`` plus the human-readable description gives the
    # model enough guidance; the tool handler still validates the value.
    enum_val = cleaned.get("enum")
    type_val = cleaned.get("type")
    if isinstance(enum_val, list) and type_val in {"integer", "number", "boolean"}:
        if any(not isinstance(item, str) for item in enum_val):
            cleaned.pop("enum", None)

    return cleaned


def sanitize_gemini_tool_parameters(parameters: Any) -> Dict[str, Any]:
    """Normalize tool parameters to a valid Gemini object schema."""

    cleaned = sanitize_gemini_schema(parameters)
    if not cleaned:
        return {"type": "object", "properties": {}}
    return cleaned


# -- parametersJsonSchema (full JSON Schema) ---------------------------------
#
# The legacy translator above is lossy: anyOf unions without an outer type, bare
# arrays, $ref/$defs and additionalProperties get stripped or repaired, and one
# unrepresentable construct 400s the ENTIRE request. Through
# ``parametersJsonSchema`` the schema goes as-is; only same-document $refs are
# inlined (MCP pydantic / zod emit them) and the root ``$schema`` is dropped.

logger = logging.getLogger(__name__)

_EMPTY_OBJECT_SCHEMA: Dict[str, Any] = {"type": "object", "properties": {}}
# Real tool schemas hold a handful of refs; the cap stops circular models from
# expanding forever.
_MAX_REF_EXPANSIONS = 256


def _resolve_local_ref(root: Dict[str, Any], ref: str) -> Optional[Dict[str, Any]]:
    """Resolve a same-document JSON pointer (``#/$defs/Foo``) against *root*."""
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return None
    node: Any = root
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, dict) else None


def _inline_refs(
    node: Any, root: Dict[str, Any], budget: List[int], stack: tuple = ()
) -> Any:
    """Recursively inline same-document ``$ref`` nodes. Raises ``ValueError`` on
    an unresolvable or circular reference or an exhausted budget."""
    if isinstance(node, list):
        return [_inline_refs(item, root, budget, stack) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if not isinstance(ref, str):
        return {
            key: _inline_refs(value, root, budget, stack) for key, value in node.items()
        }
    if ref in stack:
        raise ValueError(f"circular $ref {ref!r}")
    budget[0] -= 1
    if budget[0] < 0:
        raise ValueError("$ref expansion budget exhausted")
    target = _resolve_local_ref(root, ref)
    if target is None:
        raise ValueError(f"unresolvable $ref {ref!r}")
    inlined = _inline_refs(target, root, budget, stack + (ref,))
    # Siblings of $ref (description, default, ...) apply alongside the target and win.
    siblings = {k: v for k, v in node.items() if k != "$ref"}
    if not siblings:
        return inlined
    return {**inlined, **_inline_refs(siblings, root, budget, stack)}


def prepare_gemini_tool_parameters(parameters: Any) -> Dict[str, Any]:
    """Full JSON Schema for ``parametersJsonSchema``: deep-copied, root
    ``$schema`` dropped, same-document ``$ref`` inlined, object root guaranteed.
    A schema whose references cannot all be resolved is sent untouched so the
    provider names the real problem."""
    if not isinstance(parameters, dict) or not parameters:
        return dict(_EMPTY_OBJECT_SCHEMA)
    schema = copy.deepcopy(parameters)
    schema.pop("$schema", None)
    try:
        schema = _inline_refs(schema, schema, [_MAX_REF_EXPANSIONS])
    except ValueError as exc:
        logger.debug("Gemini tool schema kept as-is ($ref inlining skipped): %s", exc)
        return schema
    schema.pop("$defs", None)
    schema.pop("definitions", None)
    if not schema:
        return dict(_EMPTY_OBJECT_SCHEMA)
    if schema.get("type") == "object" and "properties" not in schema:
        schema["properties"] = {}
    return schema
