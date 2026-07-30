"""Gemini "Login with Google" via the Code Assist API (cloudcode-pa.googleapis.com).

The Gemini CLI's OAuth login (`~/.gemini/oauth_creds.json`) grants model access
only through Google's **Code Assist** API, which is *not* OpenAI- or
Anthropic-shaped. This module is a self-contained translator: it converts
OpenAI-style chat requests to the Code Assist envelope and Code Assist responses
back to the OpenAI chat-completions shape, so the rest of the agent runtime does
not need a new wire protocol.

Protocol grounded in the open-source google-gemini/gemini-cli
(`packages/core/src/code_assist/*`): the RPC base is
``https://cloudcode-pa.googleapis.com/v1internal`` with colon-suffixed methods
(``:loadCodeAssist``, ``:onboardUser``, ``:generateContent``,
``:streamGenerateContent?alt=sse``); the request wraps a standard Gemini
``GenerateContentRequest`` under ``{model, project, request:{...}}`` and the
response nests the real payload under ``response``.

VERIFICATION STATUS: the pure translation helpers below are unit-tested. The
live handshake + HTTP/SSE paths (``_onboard`` / ``GeminiCodeAssistClient``)
cannot be validated without a real Google login and need a one-time field test.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import httpx

CODE_ASSIST_BASE = "https://cloudcode-pa.googleapis.com/v1internal"
CLIENT_METADATA = {
    "ideType": "IDE_UNSPECIFIED",
    "platform": "PLATFORM_UNSPECIFIED",
    "pluginType": "GEMINI",
}
# UserTierId string values (gemini-cli code_assist/types.ts).
TIER_FREE = "free-tier"
TIER_LEGACY = "legacy-tier"
TIER_STANDARD = "standard-tier"

# onboardUser returns a long-running operation. For a first-time / free-tier
# login Google provisions the project asynchronously, so the initial response
# comes back ``done: false`` with no ``response`` payload; it must be polled
# until completion before the server-assigned project id is available.
_ONBOARD_POLL_INTERVAL_S = 2.0
_ONBOARD_TIMEOUT_S = 60.0


# ---------------------------------------------------------------------------
# Pure translation: OpenAI chat  ->  Gemini GenerateContentRequest
# ---------------------------------------------------------------------------

def _content_to_text(content: Any) -> str:
    """OpenAI message content may be a string or a list of parts."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: List[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    out.append(part["text"])
            elif isinstance(part, str):
                out.append(part)
        return "".join(out)
    return str(content)


def openai_messages_to_gemini(
    messages: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Return (contents, systemInstruction) in Gemini shape.

    - system messages are merged into a single ``systemInstruction``.
    - user/assistant map to roles ``user``/``model``.
    - assistant ``tool_calls`` become ``functionCall`` parts.
    - role=="tool" messages become ``functionResponse`` parts on a user turn.
    """
    system_texts: List[str] = []
    contents: List[Dict[str, Any]] = []
    # Map tool_call_id -> function name so tool results can name their function.
    call_id_to_name: Dict[str, str] = {}

    for msg in messages:
        role = msg.get("role")
        if role == "system":
            txt = _content_to_text(msg.get("content"))
            if txt:
                system_texts.append(txt)
            continue

        if role == "tool":
            name = call_id_to_name.get(str(msg.get("tool_call_id", "")), msg.get("name", "tool"))
            raw = msg.get("content")
            try:
                response_obj = json.loads(raw) if isinstance(raw, str) else raw
            except (ValueError, TypeError):
                response_obj = {"result": raw}
            if not isinstance(response_obj, dict):
                response_obj = {"result": response_obj}
            contents.append({
                "role": "user",
                "parts": [{"functionResponse": {"name": name, "response": response_obj}}],
            })
            continue

        # user / assistant
        parts: List[Dict[str, Any]] = []
        text = _content_to_text(msg.get("content"))
        if text:
            parts.append({"text": text})
        for tc in msg.get("tool_calls") or []:
            fn = (tc or {}).get("function") or {}
            name = fn.get("name", "")
            args_raw = fn.get("arguments", "{}")
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
            except ValueError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            if tc.get("id"):
                call_id_to_name[str(tc["id"])] = name
            parts.append({"functionCall": {"name": name, "args": args}})
        if not parts:
            parts.append({"text": ""})
        contents.append({"role": "model" if role == "assistant" else "user", "parts": parts})

    system_instruction = (
        {"parts": [{"text": "\n\n".join(system_texts)}]} if system_texts else None
    )
    return contents, system_instruction


def openai_tools_to_gemini(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """OpenAI ``tools`` -> Gemini ``[{"functionDeclarations": [...]}]``."""
    if not tools:
        return None
    decls: List[Dict[str, Any]] = []
    for t in tools:
        if (t or {}).get("type") != "function":
            continue
        fn = t.get("function") or {}
        decl: Dict[str, Any] = {"name": fn.get("name", "")}
        if fn.get("description"):
            decl["description"] = fn["description"]
        params = fn.get("parameters")
        if isinstance(params, dict) and params:
            decl["parameters"] = params
        decls.append(decl)
    return [{"functionDeclarations": decls}] if decls else None


def _generation_config(**kw: Any) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    mapping = {
        "temperature": "temperature",
        "top_p": "topP",
        "top_k": "topK",
        "max_tokens": "maxOutputTokens",
        "max_output_tokens": "maxOutputTokens",
        "seed": "seed",
        "stop": "stopSequences",
    }
    for src, dst in mapping.items():
        v = kw.get(src)
        if v is not None:
            cfg[dst] = v
    return cfg


def build_code_assist_request(
    *,
    model: str,
    project: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    user_prompt_id: str = "hercules",
    session_id: Optional[str] = None,
    **generation: Any,
) -> Dict[str, Any]:
    """Assemble the Code Assist ``{model, project, request:{...}}`` envelope."""
    contents, system_instruction = openai_messages_to_gemini(messages)
    inner: Dict[str, Any] = {"contents": contents}
    if system_instruction:
        inner["systemInstruction"] = system_instruction
    g_tools = openai_tools_to_gemini(tools)
    if g_tools:
        inner["tools"] = g_tools
    gcfg = _generation_config(**generation)
    if gcfg:
        inner["generationConfig"] = gcfg
    if session_id:
        inner["session_id"] = session_id
    return {
        "model": model,
        "project": project,
        "user_prompt_id": user_prompt_id,
        "request": inner,
    }


# ---------------------------------------------------------------------------
# Pure translation: Gemini response  ->  OpenAI chat-completions shape
# ---------------------------------------------------------------------------

_FINISH_MAP = {
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "content_filter",
    "RECITATION": "content_filter",
    "OTHER": "stop",
}


def _unwrap(resp: Dict[str, Any]) -> Dict[str, Any]:
    """Code Assist nests the real Gemini payload under ``response``."""
    if isinstance(resp, dict) and isinstance(resp.get("response"), dict):
        return resp["response"]
    return resp if isinstance(resp, dict) else {}


def gemini_response_to_openai_message(
    resp: Dict[str, Any], *, index: int = 0
) -> Dict[str, Any]:
    """Return an OpenAI-style choice: {index, message, finish_reason}."""
    payload = _unwrap(resp)
    candidates = payload.get("candidates") or []
    text_out: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    finish_reason = "stop"

    if candidates:
        cand = candidates[0]
        fr = cand.get("finishReason")
        if fr:
            finish_reason = _FINISH_MAP.get(fr, "stop")
        for i, part in enumerate((cand.get("content") or {}).get("parts") or []):
            if "text" in part and isinstance(part["text"], str):
                text_out.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"] or {}
                tool_calls.append({
                    "id": f"call_{index}_{i}_{fc.get('name', 'fn')}",
                    "type": "function",
                    "function": {
                        "name": fc.get("name", ""),
                        "arguments": json.dumps(fc.get("args", {}) or {}),
                    },
                })

    message: Dict[str, Any] = {"role": "assistant", "content": "".join(text_out) or None}
    if tool_calls:
        message["tool_calls"] = tool_calls
        finish_reason = "tool_calls"
    return {"index": index, "message": message, "finish_reason": finish_reason}


def gemini_usage_to_openai(resp: Dict[str, Any]) -> Optional[Dict[str, int]]:
    payload = _unwrap(resp)
    um = payload.get("usageMetadata")
    if not isinstance(um, dict):
        return None
    prompt = int(um.get("promptTokenCount", 0) or 0)
    completion = int(um.get("candidatesTokenCount", 0) or 0)
    total = int(um.get("totalTokenCount", prompt + completion) or (prompt + completion))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def gemini_response_to_openai_completion(
    resp: Dict[str, Any], *, model: str
) -> Dict[str, Any]:
    """Full non-streaming OpenAI chat.completion-shaped dict."""
    choice = gemini_response_to_openai_message(resp)
    out: Dict[str, Any] = {
        "object": "chat.completion",
        "model": model,
        "choices": [choice],
    }
    usage = gemini_usage_to_openai(resp)
    if usage:
        out["usage"] = usage
    return out


def iter_sse_json(lines: Iterable[str]) -> Iterable[Dict[str, Any]]:
    """Parse Code Assist SSE (``data:`` prefixed, blank-line delimited) into
    the sequence of JSON chunk objects. Each chunk is a full
    CaGenerateContentResponse (``{"response": {"candidates": [...]}}``)."""
    buf: List[str] = []

    def _flush():
        if not buf:
            return None
        raw = "\n".join(buf)
        buf.clear()
        try:
            return json.loads(raw)
        except ValueError:
            return None

    for line in lines:
        line = line.rstrip("\n")
        if line == "":
            obj = _flush()
            if obj is not None:
                yield obj
            continue
        if line.startswith("data:"):
            buf.append(line[len("data:"):].lstrip())
    obj = _flush()
    if obj is not None:
        yield obj


# ---------------------------------------------------------------------------
# Live client (handshake + HTTP). Grounded in spec; NEEDS a real-login field
# test — kept isolated from the pure helpers above.
# ---------------------------------------------------------------------------

def _onboard(http, headers: Dict[str, str], project_override: Optional[str]) -> str:
    """Run loadCodeAssist -> (tier) -> onboardUser and return the project id.

    Free-tier personal OAuth: project is server-assigned when no GOOGLE_CLOUD_
    PROJECT is set; returned as response.cloudaicompanionProject.id.
    """
    meta = dict(CLIENT_METADATA)
    if project_override:
        meta["duetProject"] = project_override
    load = http.post(
        f"{CODE_ASSIST_BASE}:loadCodeAssist",
        headers=headers,
        json={"cloudaicompanionProject": project_override, "metadata": meta},
    )
    load.raise_for_status()
    info = load.json()
    if info.get("cloudaicompanionProject"):
        return str(info["cloudaicompanionProject"])

    # Pick tier: currentTier, else default allowed tier, else free.
    tier_id = TIER_FREE
    current = info.get("currentTier") or {}
    if current.get("id"):
        tier_id = current["id"]
    else:
        for t in info.get("allowedTiers") or []:
            if t.get("isDefault") and t.get("id"):
                tier_id = t["id"]
                break

    # onboardUser is a long-running operation. The first call for a new user
    # returns ``done: false`` with no ``response`` payload while Google
    # provisions the project; poll until it completes (matching gemini-cli)
    # before reading the server-assigned id — otherwise we return an empty
    # project and every subsequent generateContent call fails.
    onboard_body = {
        "tierId": tier_id,
        "cloudaicompanionProject": project_override,
        "metadata": meta,
    }
    deadline = time.monotonic() + _ONBOARD_TIMEOUT_S
    op: Dict[str, Any] = {}
    while True:
        onboard = http.post(
            f"{CODE_ASSIST_BASE}:onboardUser",
            headers=headers,
            json=onboard_body,
        )
        onboard.raise_for_status()
        op = onboard.json() or {}
        # LRO convention: a completed op has ``done: true`` (and a populated
        # ``response``); an already-onboarded user may return the payload
        # immediately without ``done``.
        if op.get("done") or op.get("response"):
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(_ONBOARD_POLL_INTERVAL_S)
    # Completed long-running op: response.cloudaicompanionProject.id
    resp = op.get("response") or {}
    proj = (resp.get("cloudaicompanionProject") or {}).get("id")
    return str(proj or project_override or "")


def gemini_chunk_to_openai_chunk(
    chunk: Dict[str, Any], *, model: str, emit_role: bool = False
) -> Dict[str, Any]:
    """One Code Assist SSE chunk -> one OpenAI chat.completion.chunk dict.

    Gemini stream chunks carry incremental parts; text becomes ``delta.content``
    and functionCall parts become ``delta.tool_calls``. Pure/testable.
    """
    payload = _unwrap(chunk)
    candidates = payload.get("candidates") or []
    delta: Dict[str, Any] = {}
    if emit_role:
        delta["role"] = "assistant"
    finish_reason = None
    if candidates:
        cand = candidates[0]
        fr = cand.get("finishReason")
        if fr:
            finish_reason = _FINISH_MAP.get(fr, "stop")
        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        for i, part in enumerate((cand.get("content") or {}).get("parts") or []):
            if "text" in part and isinstance(part["text"], str):
                text_parts.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"] or {}
                tool_calls.append({
                    "index": i,
                    "id": f"call_{i}_{fc.get('name', 'fn')}",
                    "type": "function",
                    "function": {
                        "name": fc.get("name", ""),
                        "arguments": json.dumps(fc.get("args", {}) or {}),
                    },
                })
        if text_parts:
            delta["content"] = "".join(text_parts)
        if tool_calls:
            delta["tool_calls"] = tool_calls
            finish_reason = finish_reason or "tool_calls"
    return {
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


class GeminiCodeAssistTransport(httpx.BaseTransport):
    """An httpx transport that makes an OpenAI SDK client speak Code Assist.

    The OpenAI SDK builds a normal ``POST {base}/chat/completions`` request; this
    transport intercepts it, translates to the Code Assist envelope, calls
    ``cloudcode-pa.googleapis.com``, and translates the response (or SSE stream)
    back to the OpenAI chat-completions shape. So the agent runtime keeps using
    ``api_mode == 'chat_completions'`` unchanged.

    ``outbound`` is the httpx client used for the real Google call — injectable
    so the translation can be unit-tested against canned responses without a live
    login. ``project_provider`` returns the (cached) onboarded project id;
    ``token_provider`` returns a fresh bearer per request.
    """

    def __init__(
        self,
        *,
        token_provider: Callable[[], str],
        project_provider: Callable[[], str],
        user_prompt_id: str = "hercules",
        user_agent: str = "hercules-cli (GeminiCLI-compatible)",
        outbound: Optional[httpx.Client] = None,
    ) -> None:
        self._token = token_provider
        self._project = project_provider
        self._user_prompt_id = user_prompt_id
        self._user_agent = user_agent
        self._outbound = outbound or httpx.Client(timeout=600.0)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": "application/json",
            "User-Agent": self._user_agent,
        }

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        model = str(body.get("model") or "").split("/")[-1] or "gemini-2.5-pro"
        stream = bool(body.get("stream"))
        ca_req = build_code_assist_request(
            model=model,
            project=self._project(),
            messages=body.get("messages") or [],
            tools=body.get("tools"),
            user_prompt_id=self._user_prompt_id,
            temperature=body.get("temperature"),
            top_p=body.get("top_p"),
            max_tokens=body.get("max_tokens"),
            stop=body.get("stop"),
        )
        headers = self._headers()

        if stream:
            upstream = self._outbound.post(
                f"{CODE_ASSIST_BASE}:streamGenerateContent",
                params={"alt": "sse"},
                headers=headers,
                json=ca_req,
            )
            if upstream.status_code >= 400:
                return httpx.Response(upstream.status_code, content=upstream.content, request=request)

            created = int(time.time())

            def _sse_iter() -> Iterable[bytes]:
                first = True
                for chunk in iter_sse_json(upstream.iter_lines()):
                    oai = gemini_chunk_to_openai_chunk(chunk, model=model, emit_role=first)
                    oai["created"] = created
                    first = False
                    yield f"data: {json.dumps(oai)}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"

            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=_IterStream(_sse_iter()),
                request=request,
            )

        upstream = self._outbound.post(
            f"{CODE_ASSIST_BASE}:generateContent",
            headers=headers,
            json=ca_req,
        )
        if upstream.status_code >= 400:
            return httpx.Response(upstream.status_code, content=upstream.content, request=request)
        completion = gemini_response_to_openai_completion(upstream.json(), model=model)
        completion["created"] = int(time.time())
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=json.dumps(completion).encode("utf-8"),
            request=request,
        )


class _IterStream(httpx.SyncByteStream):
    """Adapt a bytes iterator into an httpx streaming response body."""

    def __init__(self, it: Iterable[bytes]) -> None:
        self._it = it

    def __iter__(self):
        return iter(self._it)

    def close(self) -> None:  # pragma: no cover - nothing to release
        pass


def make_project_provider(
    token_provider: Callable[[], str], outbound: httpx.Client
) -> Callable[[], str]:
    """Return a cached provider that runs the onboarding handshake once.

    Free-tier personal OAuth: the project id is server-assigned unless
    GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_PROJECT_ID is set.
    """
    cache: Dict[str, str] = {}

    def _get() -> str:
        if cache.get("project"):
            return cache["project"]
        headers = {
            "Authorization": f"Bearer {token_provider()}",
            "Content-Type": "application/json",
        }
        override = (
            os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GOOGLE_CLOUD_PROJECT_ID")
            or None
        )
        cache["project"] = _onboard(outbound, headers, override)
        return cache["project"]

    return _get


def build_gemini_code_assist_client(
    *,
    token_provider: Callable[[], str],
    base_url: str = CODE_ASSIST_BASE,
    timeout: float = 600.0,
):
    """Build an OpenAI SDK client whose transport speaks Code Assist.

    The returned client is a drop-in for the agent runtime's OpenAI client
    (``api_mode == 'chat_completions'``): calls to ``chat.completions.create``
    are translated to/from cloudcode-pa. ``token_provider`` supplies a fresh
    bearer per request (re-reading the refreshed creds); onboarding runs once.
    """
    from openai import OpenAI

    outbound = httpx.Client(timeout=timeout)
    transport = GeminiCodeAssistTransport(
        token_provider=token_provider,
        project_provider=make_project_provider(token_provider, outbound),
        outbound=outbound,
    )
    http_client = httpx.Client(transport=transport, base_url=base_url)
    return OpenAI(
        api_key="gemini-oauth",  # unused; the transport injects the real bearer
        base_url=base_url,
        http_client=http_client,
        max_retries=0,
    )
