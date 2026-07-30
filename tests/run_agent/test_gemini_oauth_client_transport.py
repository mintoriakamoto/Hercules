"""Regression guard: gemini-oauth clients must carry the Code Assist transport.

Gemini "Login with Google" (provider ``gemini-oauth``) reaches the model only
through Google's Code Assist API, whose RPC endpoint is
``cloudcode-pa.googleapis.com/v1internal:generateContent``. A plain OpenAI
client pointed at that base URL POSTs to ``/v1internal/chat/completions`` — a
route Google's frontend answers with a generic HTML ``Error 404 (Not Found)``,
which surfaced to users as "API call failed after 3 retries: HTTP 404".

The one-off client swap in ``agent_init`` installed the translating httpx
transport on the *shared* client, but the conversation loop builds a *fresh
per-request* client for every chat-completions call
(``_create_request_openai_client`` → ``_create_openai_client``). That rebuild
dropped the transport and hit the bare ``/chat/completions`` route.

These tests pin the fix at the single chokepoint (``create_openai_client``):
every gemini-oauth client — shared, recreated, or per-request — must carry the
``GeminiCodeAssistTransport`` so requests are translated to the Code Assist RPC.
"""
from unittest.mock import MagicMock, patch

import httpx

import agent.gemini_code_assist as g
from run_agent import AIAgent


def _gemini_oauth_agent() -> AIAgent:
    agent = AIAgent(
        api_key="gemini-oauth",
        base_url="https://cloudcode-pa.googleapis.com/v1internal",
        model="gemini-2.5-flash-lite",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    agent.provider = "gemini-oauth"
    return agent


def _underlying_transport(openai_client):
    """The httpx transport backing an OpenAI SDK client."""
    return openai_client._client._transport


def test_create_openai_client_installs_code_assist_transport():
    agent = _gemini_oauth_agent()

    client = agent._create_openai_client(
        {
            "api_key": "gemini-oauth",
            "base_url": "https://cloudcode-pa.googleapis.com/v1internal",
        },
        reason="test",
        shared=True,
    )

    assert isinstance(_underlying_transport(client), g.GeminiCodeAssistTransport), (
        "gemini-oauth clients must be built with the Code Assist translating "
        "transport, otherwise requests hit /v1internal/chat/completions and "
        "Google returns an HTML 404"
    )


def test_per_request_client_reuses_shared_code_assist_client():
    """The per-request factory must reuse the shared client (like moa) so the
    once-per-session onboarding/project cache survives, and so it never falls
    through to a plain rebuilt OpenAI client that would drop the transport."""
    agent = _gemini_oauth_agent()

    shared = agent._create_openai_client(
        {
            "api_key": "gemini-oauth",
            "base_url": "https://cloudcode-pa.googleapis.com/v1internal",
        },
        reason="test",
        shared=True,
    )
    agent.client = shared

    request_client = agent._create_request_openai_client(reason="test")

    assert request_client is shared, (
        "per-request gemini-oauth client must be the shared Code Assist client, "
        "not a freshly rebuilt plain OpenAI client"
    )
    assert isinstance(_underlying_transport(request_client), g.GeminiCodeAssistTransport)


def test_gemini_oauth_transport_targets_generate_content_rpc():
    """End-to-end at the client boundary: a chat.completions call on the built
    client must reach the Code Assist ``:generateContent`` RPC, never the
    OpenAI ``/chat/completions`` path that 404s."""
    agent = _gemini_oauth_agent()

    captured = {}

    def _fake_post(url, params=None, headers=None, json=None):
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(
            200,
            json={
                "response": {
                    "candidates": [
                        {"finishReason": "STOP", "content": {"parts": [{"text": "ok"}]}}
                    ]
                }
            },
        )

    with patch.object(g, "make_project_provider", lambda *a, **k: (lambda: "proj-1")):
        client = agent._create_openai_client(
            {
                "api_key": "gemini-oauth",
                "base_url": "https://cloudcode-pa.googleapis.com/v1internal",
            },
            reason="test",
            shared=True,
        )
        transport = _underlying_transport(client)
        transport._outbound = MagicMock(post=_fake_post)
        # Bypass on-disk OAuth creds (absent in CI): the bearer is irrelevant to
        # what this test asserts (the outbound RPC URL).
        transport._token = lambda: "fake-token"

        result = client.chat.completions.create(
            model="gemini-2.5-flash-lite",
            messages=[{"role": "user", "content": "hi"}],
        )

    assert captured["url"].endswith(":generateContent"), captured.get("url")
    assert "/chat/completions" not in captured["url"]
    assert result.choices[0].message.content == "ok"
