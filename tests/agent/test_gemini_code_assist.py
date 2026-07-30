"""Gemini Code Assist adapter — pure translation helpers (OpenAI <-> Code Assist).

These cover the stateless request/response/SSE/tool translation, grounded in the
gemini-cli code_assist protocol. The live handshake/HTTP paths are excluded
(they need a real Google login) — see the module docstring.
"""

import json

import httpx

import agent.gemini_code_assist as g


class _FakeResp:
    def __init__(self, status=200, payload=None, lines=None):
        self.status_code = status
        self._payload = payload
        self._lines = lines or []
        self.content = json.dumps(payload).encode() if payload is not None else b""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def iter_lines(self):
        return iter(self._lines)


class _FakeOutbound:
    """Stands in for the httpx client that would call cloudcode-pa."""
    def __init__(self, resp):
        self.resp = resp
        self.calls = []

    def post(self, url, params=None, headers=None, json=None):
        self.calls.append({"url": url, "params": params, "json": json, "headers": headers})
        return self.resp


class TestMessagesToGemini:
    def test_system_extracted_and_roles_mapped(self):
        contents, sysi = g.openai_messages_to_gemini([
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ])
        assert sysi == {"parts": [{"text": "be terse"}]}
        assert [c["role"] for c in contents] == ["user", "model"]
        assert contents[0]["parts"] == [{"text": "hi"}]

    def test_multiple_system_messages_merged(self):
        _, sysi = g.openai_messages_to_gemini([
            {"role": "system", "content": "a"},
            {"role": "system", "content": "b"},
            {"role": "user", "content": "x"},
        ])
        assert sysi == {"parts": [{"text": "a\n\nb"}]}

    def test_assistant_tool_call_becomes_functioncall(self):
        contents, _ = g.openai_messages_to_gemini([
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "lookup", "arguments": '{"q": "x"}'}}
            ]},
        ])
        assert contents[0]["role"] == "model"
        assert contents[0]["parts"][0] == {"functionCall": {"name": "lookup", "args": {"q": "x"}}}

    def test_tool_result_becomes_functionresponse_named_by_call_id(self):
        contents, _ = g.openai_messages_to_gemini([
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "lookup", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "c1", "content": '{"ok": true}'},
        ])
        fr = contents[1]["parts"][0]["functionResponse"]
        assert fr["name"] == "lookup"          # name resolved from the earlier call id
        assert fr["response"] == {"ok": True}
        assert contents[1]["role"] == "user"

    def test_non_json_tool_result_wrapped(self):
        contents, _ = g.openai_messages_to_gemini([
            {"role": "tool", "tool_call_id": "x", "name": "fn", "content": "plain text"},
        ])
        assert contents[0]["parts"][0]["functionResponse"]["response"] == {"result": "plain text"}

    def test_list_content_parts_flattened(self):
        contents, _ = g.openai_messages_to_gemini([
            {"role": "user", "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]},
        ])
        assert contents[0]["parts"] == [{"text": "ab"}]


class TestToolsToGemini:
    def test_openai_tools_to_function_declarations(self):
        out = g.openai_tools_to_gemini([
            {"type": "function", "function": {
                "name": "search", "description": "d",
                "parameters": {"type": "object", "properties": {}}}},
        ])
        assert out == [{"functionDeclarations": [
            {"name": "search", "description": "d", "parameters": {"type": "object", "properties": {}}}
        ]}]

    def test_none_and_empty(self):
        assert g.openai_tools_to_gemini(None) is None
        assert g.openai_tools_to_gemini([]) is None


class TestBuildRequest:
    def test_envelope_shape(self):
        req = g.build_code_assist_request(
            model="gemini-2.5-pro", project="p1",
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "f"}}],
            temperature=0.2, max_tokens=64,
        )
        assert set(req) == {"model", "project", "user_prompt_id", "request"}
        assert req["model"] == "gemini-2.5-pro"
        assert req["project"] == "p1"
        inner = req["request"]
        assert inner["contents"][0]["parts"] == [{"text": "hi"}]
        assert inner["tools"] == [{"functionDeclarations": [{"name": "f"}]}]
        assert inner["generationConfig"] == {"temperature": 0.2, "maxOutputTokens": 64}


class TestResponseToOpenAI:
    def test_text_and_usage(self):
        resp = {"response": {
            "candidates": [{"finishReason": "STOP",
                            "content": {"parts": [{"text": "hello"}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
        }}
        comp = g.gemini_response_to_openai_completion(resp, model="gemini-2.5-pro")
        assert comp["choices"][0]["message"]["content"] == "hello"
        assert comp["choices"][0]["finish_reason"] == "stop"
        assert comp["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    def test_functioncall_becomes_tool_calls(self):
        resp = {"response": {"candidates": [{
            "content": {"parts": [{"functionCall": {"name": "lookup", "args": {"q": "x"}}}]}}]}}
        choice = g.gemini_response_to_openai_message(resp)
        tc = choice["message"]["tool_calls"][0]
        assert tc["function"]["name"] == "lookup"
        assert json.loads(tc["function"]["arguments"]) == {"q": "x"}
        assert choice["finish_reason"] == "tool_calls"

    def test_max_tokens_finish_reason(self):
        resp = {"response": {"candidates": [{"finishReason": "MAX_TOKENS",
                                             "content": {"parts": [{"text": "..."}]}}]}}
        assert g.gemini_response_to_openai_message(resp)["finish_reason"] == "length"

    def test_unwrap_handles_missing_response_wrapper(self):
        # Defensive: a bare Gemini payload (already unwrapped) still parses.
        bare = {"candidates": [{"content": {"parts": [{"text": "z"}]}}]}
        assert g.gemini_response_to_openai_message(bare)["message"]["content"] == "z"


class TestSSE:
    def test_data_prefixed_blank_delimited(self):
        lines = [
            'data: {"response":{"candidates":[{"content":{"parts":[{"text":"a"}]}}]}}',
            '',
            'data: {"response":{"candidates":[{"content":{"parts":[{"text":"b"}]}}]}}',
            '',
        ]
        chunks = list(g.iter_sse_json(lines))
        assert len(chunks) == 2
        assert g.gemini_response_to_openai_message(chunks[0])["message"]["content"] == "a"
        assert g.gemini_response_to_openai_message(chunks[1])["message"]["content"] == "b"

    def test_multiline_data_joined(self):
        lines = ['data: {"response":', 'data: {"candidates":[]}}', '']
        chunks = list(g.iter_sse_json(lines))
        assert chunks == [{"response": {"candidates": []}}]

    def test_malformed_chunk_skipped(self):
        lines = ['data: not json', '', 'data: {"response":{"candidates":[]}}', '']
        chunks = list(g.iter_sse_json(lines))
        assert chunks == [{"response": {"candidates": []}}]


class TestTransportNonStreaming:
    def _resp(self):
        return {"response": {
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "hi there"}]}}],
            "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2, "totalTokenCount": 5},
        }}

    def test_translates_request_and_response(self):
        ob = _FakeOutbound(_FakeResp(payload=self._resp()))
        t = g.GeminiCodeAssistTransport(
            token_provider=lambda: "tok", project_provider=lambda: "proj-1", outbound=ob)
        client = httpx.Client(transport=t, base_url="https://gemini.local/v1")
        out = client.post("/chat/completions", json={
            "model": "gemini/gemini-2.5-pro",
            "messages": [{"role": "user", "content": "hi"}]}).json()
        assert out["choices"][0]["message"]["content"] == "hi there"
        assert out["choices"][0]["finish_reason"] == "stop"
        assert out["usage"] == {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
        # outbound call shape
        call = ob.calls[0]
        assert call["url"].endswith(":generateContent")
        assert call["json"]["model"] == "gemini-2.5-pro"   # provider prefix stripped
        assert call["json"]["project"] == "proj-1"
        assert call["headers"]["Authorization"] == "Bearer tok"

    def test_upstream_error_passthrough(self):
        ob = _FakeOutbound(_FakeResp(status=403, payload={"error": "denied"}))
        t = g.GeminiCodeAssistTransport(
            token_provider=lambda: "tok", project_provider=lambda: "p", outbound=ob)
        client = httpx.Client(transport=t, base_url="https://gemini.local/v1")
        r = client.post("/chat/completions", json={"model": "gemini-2.5-pro", "messages": []})
        assert r.status_code == 403


class TestTransportStreaming:
    def test_streams_openai_chunks(self):
        sse = [
            'data: {"response":{"candidates":[{"content":{"parts":[{"text":"Hel"}]}}]}}', '',
            'data: {"response":{"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":"lo"}]}}]}}', '',
        ]
        ob = _FakeOutbound(_FakeResp(lines=sse))
        t = g.GeminiCodeAssistTransport(
            token_provider=lambda: "tok", project_provider=lambda: "p", outbound=ob)
        client = httpx.Client(transport=t, base_url="https://gemini.local/v1")
        chunks = []
        with client.stream("POST", "/chat/completions", json={
                "model": "gemini-2.5-flash", "stream": True,
                "messages": [{"role": "user", "content": "hi"}]}) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: ") and "[DONE]" not in line:
                    chunks.append(json.loads(line[6:]))
        assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
        assert "".join(c["choices"][0]["delta"].get("content", "") for c in chunks) == "Hello"
        assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
        assert ob.calls[0]["url"].endswith(":streamGenerateContent")
        assert ob.calls[0]["params"] == {"alt": "sse"}


class _SeqOutbound:
    """Fake client that replays a scripted response per endpoint.

    ``load`` is returned for ``:loadCodeAssist``; ``onboard`` is a queue of
    responses popped one-per-call for ``:onboardUser`` (to exercise the
    long-running-operation polling loop).
    """
    def __init__(self, load, onboard):
        self.load = load
        self.onboard = list(onboard)
        self.calls = []

    def post(self, url, params=None, headers=None, json=None):
        self.calls.append(url)
        if url.endswith(":loadCodeAssist"):
            return self.load
        if url.endswith(":onboardUser"):
            return self.onboard.pop(0)
        raise AssertionError(f"unexpected url {url}")


class TestOnboardPolling:
    def test_polls_onboard_until_done_then_returns_project(self, monkeypatch):
        # Don't actually sleep between polls.
        monkeypatch.setattr(g, "_ONBOARD_POLL_INTERVAL_S", 0)
        load = _FakeResp(payload={"allowedTiers": [{"id": "free-tier", "isDefault": True}]})
        ob = _SeqOutbound(
            load=load,
            onboard=[
                _FakeResp(payload={"done": False}),
                _FakeResp(payload={"done": False}),
                _FakeResp(payload={"done": True, "response": {
                    "cloudaicompanionProject": {"id": "proj-123"}}}),
            ],
        )
        proj = g._onboard(ob, {"Authorization": "Bearer x"}, None)
        assert proj == "proj-123"
        # loadCodeAssist once + onboardUser three times (two pending, one done).
        assert ob.calls.count("https://cloudcode-pa.googleapis.com/v1internal:onboardUser") == 3

    def test_immediate_project_from_load_skips_onboard(self):
        load = _FakeResp(payload={"cloudaicompanionProject": "existing-proj"})
        ob = _SeqOutbound(load=load, onboard=[])
        proj = g._onboard(ob, {"Authorization": "Bearer x"}, None)
        assert proj == "existing-proj"
        assert all(not u.endswith(":onboardUser") for u in ob.calls)


class TestChunkHelper:
    def test_functioncall_delta(self):
        chunk = {"response": {"candidates": [{"content": {"parts": [
            {"functionCall": {"name": "f", "args": {"a": 1}}}]}}]}}
        oai = g.gemini_chunk_to_openai_chunk(chunk, model="m", emit_role=True)
        tc = oai["choices"][0]["delta"]["tool_calls"][0]
        assert tc["function"]["name"] == "f"
        assert json.loads(tc["function"]["arguments"]) == {"a": 1}
        assert oai["choices"][0]["finish_reason"] == "tool_calls"
