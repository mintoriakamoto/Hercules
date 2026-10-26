"""Schema validation and structured data definitions.

Uses JSON Schema for runtime validation of all data passing between
components. Ensures type safety and contract enforcement.
"""

import json
from pathlib import Path
from typing import Any, Dict

try:
    import jsonschema
except ImportError:
    jsonschema = None


class SchemaValidator:
    """Validates data against JSON schemas."""

    _schemas: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def load_schemas(cls):
        """Load all schemas from schema directory."""
        schema_dir = Path(__file__).parent
        for schema_file in schema_dir.glob("*.schema.json"):
            with open(schema_file, encoding="utf-8") as f:
                schema_data = json.load(f)
                schema_name = schema_file.stem
                cls._schemas[schema_name] = schema_data

    @classmethod
    def validate_message(cls, data: Dict[str, Any]) -> bool:
        """Validate a message against schema."""
        if jsonschema is None:
            return True

        if not cls._schemas:
            cls.load_schemas()

        schema = cls._schemas.get("messages", {})
        message_schema = schema.get("definitions", {}).get("Message", {})

        try:
            jsonschema.validate(data, message_schema)
            return True
        except jsonschema.ValidationError as e:
            raise ValueError(f"Invalid message: {e.message}") from e

    @classmethod
    def validate_tool_call(cls, data: Dict[str, Any]) -> bool:
        """Validate a tool call against schema."""
        if jsonschema is None:
            return True

        if not cls._schemas:
            cls.load_schemas()

        schema = cls._schemas.get("messages", {})
        tool_schema = schema.get("definitions", {}).get("ToolCall", {})

        try:
            jsonschema.validate(data, tool_schema)
            return True
        except jsonschema.ValidationError as e:
            raise ValueError(f"Invalid tool call: {e.message}") from e


__all__ = ["SchemaValidator"]
