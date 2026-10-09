"""Tests for agent.gemini_schema — OpenAI→Gemini tool parameter translation."""

import copy

from agent.gemini_schema import (
    prepare_gemini_tool_parameters,
    sanitize_gemini_schema,
    sanitize_gemini_tool_parameters,
)


class TestSanitizeGeminiSchema:
    def test_strips_unknown_top_level_keys(self):
        """$schema / additionalProperties etc. must not reach Gemini."""
        schema = {
            "type": "object",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "additionalProperties": False,
            "properties": {"foo": {"type": "string"}},
        }
        cleaned = sanitize_gemini_schema(schema)
        assert "$schema" not in cleaned
        assert "additionalProperties" not in cleaned
        assert cleaned["type"] == "object"
        assert cleaned["properties"] == {"foo": {"type": "string"}}

    def test_preserves_string_enums(self):
        """String-valued enums are valid for Gemini and must pass through."""
        schema = {"type": "string", "enum": ["pending", "done", "cancelled"]}
        cleaned = sanitize_gemini_schema(schema)
        assert cleaned["type"] == "string"
        assert cleaned["enum"] == ["pending", "done", "cancelled"]

    def test_drops_integer_enum_to_satisfy_gemini(self):
        """Gemini rejects int-typed enums; the sanitizer must drop the enum.

        Regression for the Discord tool's ``auto_archive_duration``:
        ``{type: integer, enum: [60, 1440, 4320, 10080]}`` caused
        Gemini HTTP 400 INVALID_ARGUMENT
        "Invalid value ... (TYPE_STRING), 60" on every request that
        shipped the full tool catalog to generativelanguage.googleapis.com.
        """
        schema = {
            "type": "integer",
            "enum": [60, 1440, 4320, 10080],
            "description": "Minutes (60, 1440, 4320, 10080).",
        }
        cleaned = sanitize_gemini_schema(schema)
        assert cleaned["type"] == "integer"
        assert "enum" not in cleaned
        # description must survive so the model still sees the allowed values
        assert cleaned["description"].startswith("Minutes")

    def test_drops_number_enum(self):
        """Same rule applies to ``type: number``."""
        schema = {"type": "number", "enum": [0.5, 1.0, 2.0]}
        cleaned = sanitize_gemini_schema(schema)
        assert cleaned["type"] == "number"
        assert "enum" not in cleaned

    def test_drops_boolean_enum(self):
        """And to ``type: boolean`` (Gemini rejects non-string entries)."""
        schema = {"type": "boolean", "enum": [True, False]}
        cleaned = sanitize_gemini_schema(schema)
        assert cleaned["type"] == "boolean"
        assert "enum" not in cleaned

    def test_keeps_string_enum_even_when_numeric_values_coexist_as_strings(self):
        """Stringified-numeric enums ARE valid for Gemini; don't drop them."""
        schema = {"type": "string", "enum": ["60", "1440", "4320", "10080"]}
        cleaned = sanitize_gemini_schema(schema)
        assert cleaned["enum"] == ["60", "1440", "4320", "10080"]

    def test_drops_nested_integer_enum_inside_properties(self):
        """The fix must apply recursively — the Discord case is nested."""
        schema = {
            "type": "object",
            "properties": {
                "auto_archive_duration": {
                    "type": "integer",
                    "enum": [60, 1440, 4320, 10080],
                    "description": "Thread archive duration in minutes.",
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "archived"],
                },
            },
        }
        cleaned = sanitize_gemini_schema(schema)
        props = cleaned["properties"]
        # Integer enum is dropped...
        assert props["auto_archive_duration"]["type"] == "integer"
        assert "enum" not in props["auto_archive_duration"]
        # ...but the sibling string enum is preserved.
        assert props["status"]["enum"] == ["active", "archived"]

    def test_drops_integer_enum_inside_array_items(self):
        """Array item schemas recurse through ``items``."""
        schema = {
            "type": "array",
            "items": {"type": "integer", "enum": [1, 2, 3]},
        }
        cleaned = sanitize_gemini_schema(schema)
        assert cleaned["items"]["type"] == "integer"
        assert "enum" not in cleaned["items"]

    def test_non_dict_input_returns_empty(self):
        assert sanitize_gemini_schema(None) == {}
        assert sanitize_gemini_schema("not a schema") == {}
        assert sanitize_gemini_schema([1, 2, 3]) == {}


class TestSanitizeGeminiToolParameters:
    def test_empty_parameters_return_valid_object_schema(self):
        """Gemini requires ``parameters`` to be a valid object schema."""
        cleaned = sanitize_gemini_tool_parameters({})
        assert cleaned == {"type": "object", "properties": {}}

    def test_discord_create_thread_parameters_no_longer_trip_gemini(self):
        """End-to-end regression: the exact shape that was rejected in prod."""
        params = {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create_thread"]},
                "auto_archive_duration": {
                    "type": "integer",
                    "enum": [60, 1440, 4320, 10080],
                    "description": "Thread archive duration in minutes "
                    "(create_thread, default 1440).",
                },
            },
            "required": ["action"],
        }
        cleaned = sanitize_gemini_tool_parameters(params)
        aad = cleaned["properties"]["auto_archive_duration"]
        # The field that triggered the Gemini 400 is gone.
        assert "enum" not in aad
        # Type + description survive so the model still knows what to send.
        assert aad["type"] == "integer"
        assert "1440" in aad["description"]
        # And the string-enum sibling is untouched.
        assert cleaned["properties"]["action"]["enum"] == ["create_thread"]


# -- parametersJsonSchema (full JSON Schema) path ----------------------------


class TestPrepareGeminiToolParameters:
    def test_full_json_schema_survives_and_input_is_not_mutated(self):
        params = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "globs": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ]
                },
                "bare_array": {"type": "array"},
                "opts": {"type": "object", "additionalProperties": {"type": "string"}},
            },
            "required": ["globs"],
        }
        original = copy.deepcopy(params)
        out = prepare_gemini_tool_parameters(params)
        assert params == original
        assert "$schema" not in out
        assert out["properties"]["globs"]["anyOf"][1] == {
            "type": "array",
            "items": {"type": "string"},
        }
        assert out["properties"]["bare_array"] == {"type": "array"}
        assert out["properties"]["opts"]["additionalProperties"] == {"type": "string"}
        assert prepare_gemini_tool_parameters({}) == {
            "type": "object",
            "properties": {},
        }

    def test_local_refs_inlined_with_sibling_override_and_defs_dropped(self):
        params = {
            "type": "object",
            "properties": {"user": {"$ref": "#/$defs/User", "description": "who"}},
            "$defs": {
                "User": {
                    "type": "object",
                    "description": "generic",
                    "properties": {
                        "tags": {"type": "array", "items": {"$ref": "#/$defs/Tag"}}
                    },
                },
                "Tag": {"type": "string"},
            },
        }
        out = prepare_gemini_tool_parameters(params)
        assert "$defs" not in out
        user = out["properties"]["user"]
        assert user["description"] == "who"
        assert user["properties"]["tags"]["items"] == {"type": "string"}

    def test_unresolvable_or_circular_ref_passes_schema_through_untouched(self):
        loop = {
            "Loop": {"type": "object", "properties": {"next": {"$ref": "#/$defs/Loop"}}}
        }
        for defs in (loop, {}):
            params = {
                "type": "object",
                "properties": {"p": {"$ref": "#/$defs/Loop"}},
                "$defs": defs,
            }
            out = prepare_gemini_tool_parameters(params)
            assert out["properties"]["p"] == {"$ref": "#/$defs/Loop"}
            assert out["$defs"] == defs


class TestAdapterWireShape:
    _TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "t",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "g": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}},
                            ]
                        }
                    },
                },
            },
        }
    ]

    def _decl(self, base_url):
        from agent.gemini_native_adapter import (
            build_gemini_request,
            gemini_accepts_parameters_json_schema,
        )

        request = build_gemini_request(
            messages=[{"role": "user", "content": "hi"}],
            tools=self._TOOLS,
            tools_as_json_schema=gemini_accepts_parameters_json_schema(base_url),
        )
        return request["tools"][0]["functionDeclarations"][0]

    def test_v1beta_sends_parameters_json_schema(self):
        beta = self._decl("https://generativelanguage.googleapis.com/v1beta/")
        assert "parameters" not in beta
        items = beta["parametersJsonSchema"]["properties"]["g"]["anyOf"][1]["items"]
        assert items == {"type": "string"}

    def test_other_versions_keep_legacy_subset(self):
        v1 = self._decl("https://generativelanguage.googleapis.com/v1")
        assert "parametersJsonSchema" not in v1
        assert v1["parameters"]["properties"]["g"]
