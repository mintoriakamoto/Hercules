#!/usr/bin/env python3
"""Shared blackboard — the inter-agent communication channel.

Subagents run in-process (``tools/delegate_tool.py`` executes them on a
ThreadPoolExecutor), but each child gets a fresh conversation with no view of
the parent's context, and siblings can't see each other at all. The kanban
swarm has a blackboard (``hercules_cli/kanban_swarm.py``), but it lives on a
kanban root card and is only reachable through kanban plumbing — a plain
``delegate_task`` fan-out has nothing.

This module merges that gap: a general-purpose, SQLite-backed blackboard any
agent in the process tree can post to and read from, using the same
merge-by-key / last-writer-wins / author-traceability semantics as the swarm
blackboard. Parent posts task context before fanning out; workers post
findings as they go; siblings and the parent read the merged board at any
time. It is SHORT-TERM shared memory scoped to a board id — unlike MEMORY.md
(long-term, user-curated, deliberately blocked for subagents), the blackboard
is expendable coordination state.

Board resolution (first match wins):
  1. explicit ``board`` argument
  2. ``HERCULES_BLACKBOARD_BOARD`` environment variable — set it once in the
     parent process and every in-process subagent inherits it automatically
  3. ``"default"``

Storage: ``$HERCULES_HOME/blackboard.db`` (WAL journal, per-call connections,
busy-timeout) — safe for the parent plus N worker threads writing
concurrently.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from tools.registry import registry, tool_error

# Serialize first-touch schema creation: N worker threads opening a fresh
# database concurrently would otherwise race the WAL switch + CREATE TABLE.
_init_lock = threading.Lock()
_initialized_paths: set[str] = set()

_ENV_BOARD = "HERCULES_BLACKBOARD_BOARD"
_DEFAULT_BOARD = "default"
# Boards are coordination state, not archives — cap what a single read can
# return so a chatty swarm can't flood the caller's context window.
_MAX_VALUE_CHARS = 20_000
_MAX_READ_CHARS = 60_000


def _db_path() -> Path:
    override = os.environ.get("HERCULES_BLACKBOARD_DB")
    if override:
        return Path(override)
    from hercules_constants import get_hercules_home

    return get_hercules_home() / "blackboard.db"


def _connect() -> sqlite3.Connection:
    path = _db_path()
    key = str(path)
    if key not in _initialized_paths:
        with _init_lock:
            if key not in _initialized_paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                init = sqlite3.connect(path, timeout=10.0)
                try:
                    init.execute("PRAGMA journal_mode=WAL")
                    init.execute(
                        "CREATE TABLE IF NOT EXISTS blackboard_entries ("
                        " seq INTEGER PRIMARY KEY AUTOINCREMENT,"
                        " board TEXT NOT NULL,"
                        " key TEXT NOT NULL,"
                        " value TEXT NOT NULL,"
                        " author TEXT NOT NULL,"
                        " created_at REAL NOT NULL)"
                    )
                    init.execute(
                        "CREATE INDEX IF NOT EXISTS idx_blackboard_board"
                        " ON blackboard_entries (board, seq)"
                    )
                    init.execute(
                        "CREATE TABLE IF NOT EXISTS blackboard_claims ("
                        " board TEXT NOT NULL,"
                        " key TEXT NOT NULL,"
                        " owner TEXT NOT NULL,"
                        " expires_at REAL NOT NULL,"
                        " created_at REAL NOT NULL,"
                        " PRIMARY KEY (board, key))"
                    )
                    init.commit()
                finally:
                    init.close()
                _initialized_paths.add(key)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def _resolve_board(board: Optional[str]) -> str:
    text = (board or "").strip()
    if text:
        return text
    return os.environ.get(_ENV_BOARD, "").strip() or _DEFAULT_BOARD


def _normalize_value(raw: str) -> str:
    """Store canonical JSON when the value parses as JSON, raw text otherwise."""
    text = raw.strip()
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, sort_keys=True)
    except (json.JSONDecodeError, ValueError):
        return json.dumps(text, ensure_ascii=False)


def post(key: str, value: str, *, author: str = "agent", board: Optional[str] = None) -> dict[str, Any]:
    """Append one update; later posts to the same key win on read."""
    key = (key or "").strip()
    if not key:
        raise ValueError("key is required")
    if len(value or "") > _MAX_VALUE_CHARS:
        raise ValueError(
            f"value too large ({len(value)} chars > {_MAX_VALUE_CHARS}); "
            "post a summary and keep bulk data in a file, passing its path"
        )
    resolved = _resolve_board(board)
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO blackboard_entries (board, key, value, author, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (resolved, key, _normalize_value(value or ""), (author or "agent").strip() or "agent", time.time()),
        )
        return {"board": resolved, "key": key, "seq": cur.lastrowid}


def read(*, board: Optional[str] = None, key: Optional[str] = None) -> dict[str, Any]:
    """Merged view of a board: latest value per key, with author traceability.

    Same semantics as ``hercules_cli.kanban_swarm.latest_blackboard`` — later
    entries replace earlier values for the same key; ``_authors`` maps each
    key to the author of the winning value.
    """
    resolved = _resolve_board(board)
    merged: dict[str, Any] = {}
    authors: dict[str, str] = {}
    with _connect() as conn:
        rows = conn.execute(
            "SELECT key, value, author FROM blackboard_entries"
            " WHERE board = ? ORDER BY seq",
            (resolved,),
        ).fetchall()
    for row_key, row_value, row_author in rows:
        try:
            merged[row_key] = json.loads(row_value)
        except (json.JSONDecodeError, ValueError):
            merged[row_key] = row_value
        authors[row_key] = row_author
    if key is not None and key.strip():
        wanted = key.strip()
        return {
            "board": resolved,
            "entries": {wanted: merged[wanted]} if wanted in merged else {},
            "_authors": {wanted: authors[wanted]} if wanted in authors else {},
        }
    return {"board": resolved, "entries": merged, "_authors": authors}


def conflicts(*, board: Optional[str] = None) -> dict[str, Any]:
    """Keys where different authors posted different values.

    ``read`` is last-writer-wins, so one agent silently overwriting a
    sibling's finding is indistinguishable from no disagreement at all — the
    parent sees a single confident value and never learns two workers
    disagreed. This reports each contested key with the latest value from
    every author that wrote it, so the disagreement is visible and can be
    adjudicated instead of being resolved by whoever happened to finish last.
    """
    resolved = _resolve_board(board)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT key, value, author FROM blackboard_entries"
            " WHERE board = ? ORDER BY seq",
            (resolved,),
        ).fetchall()

    # Latest raw (still-serialized) value per (key, author): comparing the
    # canonical stored form means formatting differences aren't false positives.
    latest_by_key: dict[str, dict[str, str]] = {}
    for row_key, row_value, row_author in rows:
        latest_by_key.setdefault(row_key, {})[row_author] = row_value

    contested = []
    for row_key, by_author in sorted(latest_by_key.items()):
        if len(by_author) < 2 or len(set(by_author.values())) < 2:
            continue
        positions = []
        for row_author, row_value in sorted(by_author.items()):
            try:
                parsed: Any = json.loads(row_value)
            except (json.JSONDecodeError, ValueError):
                parsed = row_value
            positions.append({"author": row_author, "value": parsed})
        contested.append({"key": row_key, "positions": positions})
    return {"board": resolved, "conflicts": contested}


def _latest_positions(key: str, board: str) -> dict[str, str]:
    """Each author's most recent raw value for ``key`` on ``board``."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT value, author FROM blackboard_entries"
            " WHERE board = ? AND key = ? ORDER BY seq",
            (board, key),
        ).fetchall()
    latest: dict[str, str] = {}
    for row_value, row_author in rows:
        latest[row_author] = row_value
    return latest


def consensus(
    key: str,
    *,
    board: Optional[str] = None,
    min_support: Optional[int] = None,
) -> dict[str, Any]:
    """Agree on ``key`` only when a strict majority of authors agree.

    Aggregating N independent answers by majority is markedly more robust to
    wrong or hostile agents than debating or plurality-voting them: a
    dissenting minority can withhold agreement but cannot manufacture it.
    That property is why this reports ``agreed: None`` when the threshold
    isn't met instead of falling back to the most popular answer — a
    plurality rule hands the result to whichever faction is largest, which is
    exactly the failure a malicious minority exploits.

    One vote per author, counted on each author's latest position, so an
    agent cannot inflate its own support by posting repeatedly.
    """
    key = (key or "").strip()
    if not key:
        raise ValueError("key is required")
    resolved = _resolve_board(board)
    positions = _latest_positions(key, resolved)
    total = len(positions)

    tally: dict[str, list[str]] = {}
    for author, raw_value in positions.items():
        tally.setdefault(raw_value, []).append(author)

    threshold = total // 2 + 1 if min_support is None else max(1, int(min_support))

    agreed_raw: Optional[str] = None
    support: list[str] = []
    for raw_value, backers in tally.items():
        if len(backers) >= threshold and len(backers) > len(support):
            agreed_raw, support = raw_value, backers

    def _decode(raw: str) -> Any:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return raw

    dissent = [
        {"author": author, "value": _decode(raw_value)}
        for author, raw_value in sorted(positions.items())
        if agreed_raw is None or raw_value != agreed_raw
    ]
    return {
        "board": resolved,
        "key": key,
        "agreed": _decode(agreed_raw) if agreed_raw is not None else None,
        "has_consensus": agreed_raw is not None,
        "support": len(support),
        "total_authors": total,
        "required": threshold,
        "dissent": dissent,
    }


def boards() -> list[dict[str, Any]]:
    """All boards with entry counts, newest activity first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT board, COUNT(*), MAX(created_at) FROM blackboard_entries"
            " GROUP BY board ORDER BY MAX(created_at) DESC"
        ).fetchall()
    return [{"board": b, "entries": n, "last_post_at": ts} for b, n, ts in rows]


def wait(
    key: str,
    *,
    board: Optional[str] = None,
    timeout_seconds: float = 60.0,
    poll_interval: float = 0.25,
) -> dict[str, Any]:
    """Block until ``key`` exists on the board, or the timeout elapses.

    Turns the blackboard into dataflow: a worker can start the moment a
    sibling posts the entry it depends on, instead of busy-polling from the
    model loop (each model-driven poll costs a full tool round-trip; this
    waits in-process for pennies). Returns the same shape as a single-key
    ``read`` plus ``waited_seconds``. If the key never appears, raises
    TimeoutError — callers should treat that as "the producer didn't
    deliver", not retry forever.
    """
    key = (key or "").strip()
    if not key:
        raise ValueError("key is required")
    timeout_seconds = min(max(float(timeout_seconds), 0.0), 300.0)
    deadline = time.monotonic() + timeout_seconds
    start = time.monotonic()
    while True:
        result = read(board=board, key=key)
        if key in result["entries"]:
            result["waited_seconds"] = round(time.monotonic() - start, 3)
            return result
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"key {key!r} did not appear on board {result['board']!r} "
                f"within {timeout_seconds:g}s"
            )
        time.sleep(poll_interval)


def clear(*, board: Optional[str] = None, key: Optional[str] = None) -> dict[str, Any]:
    """Drop a whole board, or a single key on a board."""
    resolved = _resolve_board(board)
    with _connect() as conn:
        if key is not None and key.strip():
            cur = conn.execute(
                "DELETE FROM blackboard_entries WHERE board = ? AND key = ?",
                (resolved, key.strip()),
            )
        else:
            cur = conn.execute(
                "DELETE FROM blackboard_entries WHERE board = ?", (resolved,)
            )
        return {"board": resolved, "deleted": cur.rowcount}


# Claims are advisory leases, not locks. A holder that dies lets its lease
# lapse and the next caller takes the key over; a permanent lock would strand
# the work forever, which is the wrong failure mode for a swarm where a child
# can vanish mid-task.
_DEFAULT_CLAIM_TTL = 300.0
_MAX_CLAIM_TTL = 3600.0


def claim(
    key: str,
    *,
    owner: str,
    ttl_seconds: float = _DEFAULT_CLAIM_TTL,
    board: Optional[str] = None,
) -> dict[str, Any]:
    """Take an advisory lease on ``key``, or report who already holds it.

    Concurrent callers race inside SQLite and exactly one wins: the upsert
    only overwrites a row whose lease has expired, so a live holder is never
    displaced. The holder renewing its own lease always succeeds.
    """
    key = (key or "").strip()
    if not key:
        raise ValueError("key is required")
    owner = (owner or "").strip()
    if not owner:
        raise ValueError("owner is required — a lease must be attributable")
    ttl = min(max(float(ttl_seconds), 1.0), _MAX_CLAIM_TTL)
    resolved = _resolve_board(board)
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO blackboard_claims (board, key, owner, expires_at, created_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(board, key) DO UPDATE SET"
            "  owner = excluded.owner,"
            "  expires_at = excluded.expires_at,"
            "  created_at = excluded.created_at"
            " WHERE blackboard_claims.expires_at <= excluded.created_at"
            "  OR blackboard_claims.owner = excluded.owner",
            (resolved, key, owner, now + ttl, now),
        )
        held_by, expires_at = conn.execute(
            "SELECT owner, expires_at FROM blackboard_claims"
            " WHERE board = ? AND key = ?",
            (resolved, key),
        ).fetchone()
    return {
        "board": resolved,
        "key": key,
        "acquired": held_by == owner,
        "owner": held_by,
        "expires_at": expires_at,
        "expires_in_seconds": round(max(0.0, expires_at - time.time()), 3),
    }


def release(key: str, *, owner: str, board: Optional[str] = None) -> dict[str, Any]:
    """Drop a lease you hold. Releasing a lease you don't hold is a no-op."""
    key = (key or "").strip()
    if not key:
        raise ValueError("key is required")
    owner = (owner or "").strip()
    if not owner:
        raise ValueError("owner is required")
    resolved = _resolve_board(board)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM blackboard_claims WHERE board = ? AND key = ? AND owner = ?",
            (resolved, key, owner),
        )
    return {"board": resolved, "key": key, "released": cur.rowcount > 0}


def claims(*, board: Optional[str] = None) -> dict[str, Any]:
    """Live leases on a board, soonest to expire first. Expired rows are dropped."""
    resolved = _resolve_board(board)
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "DELETE FROM blackboard_claims WHERE board = ? AND expires_at <= ?",
            (resolved, now),
        )
        rows = conn.execute(
            "SELECT key, owner, expires_at FROM blackboard_claims"
            " WHERE board = ? ORDER BY expires_at",
            (resolved,),
        ).fetchall()
    return {
        "board": resolved,
        "claims": [
            {
                "key": k,
                "owner": o,
                "expires_in_seconds": round(max(0.0, exp - now), 3),
            }
            for k, o, exp in rows
        ],
    }


def blackboard_tool(
    action: str,
    key: str = "",
    value: str = "",
    author: str = "",
    board: str = "",
    timeout_seconds: float = 60.0,
    ttl_seconds: float = _DEFAULT_CLAIM_TTL,
    min_support: int = 0,
) -> str:
    """Tool entry point — dispatch on action, return JSON."""
    act = (action or "").strip().lower()
    try:
        if act == "post":
            result: Any = post(key, value, author=author or "agent", board=board or None)
        elif act == "wait":
            try:
                result = wait(key, board=board or None, timeout_seconds=timeout_seconds)
            except TimeoutError as exc:
                return tool_error(
                    f"{exc}. The producer has not posted yet — either wait again, "
                    "proceed without this input, or check whether the producing "
                    "agent failed."
                )
        elif act == "read":
            result = read(board=board or None, key=key or None)
            payload = json.dumps(result, ensure_ascii=False)
            if len(payload) > _MAX_READ_CHARS:
                result = {
                    "board": result["board"],
                    "truncated": True,
                    "keys": sorted(result["entries"].keys()),
                    "hint": "board too large to inline; read individual keys with the key parameter",
                }
        elif act == "boards":
            result = boards()
        elif act == "clear":
            result = clear(board=board or None, key=key or None)
        elif act == "claim":
            result = claim(
                key,
                owner=author or "agent",
                ttl_seconds=ttl_seconds,
                board=board or None,
            )
        elif act == "release":
            result = release(key, owner=author or "agent", board=board or None)
        elif act == "claims":
            result = claims(board=board or None)
        elif act == "conflicts":
            result = conflicts(board=board or None)
        elif act == "consensus":
            result = consensus(
                key,
                board=board or None,
                min_support=int(min_support) if min_support else None,
            )
        else:
            return tool_error(
                f"unknown action {action!r}; use post, read, wait, boards, "
                "clear, claim, release, or claims"
            )
    except (ValueError, sqlite3.Error) as exc:
        return tool_error(str(exc))
    return json.dumps(result, ensure_ascii=False)


BLACKBOARD_SCHEMA = {
    "name": "blackboard",
    "description": (
        "Shared blackboard for agent-to-agent communication. All agents in this "
        "process — you and every subagent spawned via delegate_task — see the "
        "same board, so use it to pass state that must cross agent boundaries: "
        "post task context before delegating, have workers post findings under "
        "agreed keys, read the merged board to pick up what siblings or the "
        "parent published. Reads return the LATEST value per key "
        "(last-writer-wins) plus an _authors map showing who wrote each "
        "winning value. This is short-term coordination state, not persistent "
        "memory — use the memory tool for durable cross-session knowledge. "
        "Actions: post (requires key + value; value may be plain text or a "
        "JSON document), read (whole board, or one key), wait (block until a "
        "key appears — use this instead of repeatedly reading when you depend "
        "on another agent's entry; errors on timeout), boards (list boards), "
        "clear (a board, or one key). The board defaults to the shared "
        "session board; pass board explicitly only to segregate workstreams. "
        "To avoid duplicating a sibling's work, call claim with the unit of "
        "work as the key before starting it and only proceed when the reply "
        "says acquired=true; otherwise another agent already has it, so pick "
        "up something else. Claims are time-limited leases, so a claim held "
        "by an agent that dies is automatically reclaimable — for long work, "
        "claim again to extend it, and release when you finish. Use claims to "
        "see what is currently taken. Because reads are last-writer-wins, a "
        "sibling overwriting your finding looks the same as agreement: use "
        "conflicts to list keys where different authors posted different "
        "values, and reconcile those before relying on them. When a question "
        "matters enough to answer redundantly, have each agent post its own "
        "answer under one shared key and read it back with consensus: that "
        "reports agreement only when a majority of authors agree, and returns "
        "no agreement rather than the most popular answer when they don't, so "
        "a wrong minority cannot carry the result. It costs an agent per "
        "answer, so reserve it for decisions worth paying for."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "post",
                    "read",
                    "wait",
                    "boards",
                    "clear",
                    "claim",
                    "release",
                    "claims",
                    "conflicts",
                    "consensus",
                ],
                "description": "Operation to perform.",
            },
            "min_support": {
                "type": "integer",
                "description": (
                    "For consensus: how many agreeing authors are required. "
                    "Defaults to a strict majority of the authors who posted."
                ),
            },
            "ttl_seconds": {
                "type": "number",
                "description": (
                    "For claim: how long the lease lasts before another agent "
                    "may take the key over (default 300, max 3600). Set it to "
                    "roughly how long the work should take."
                ),
            },
            "key": {
                "type": "string",
                "description": "Entry key (required for post and wait; optional filter for read/clear).",
            },
            "timeout_seconds": {
                "type": "number",
                "description": (
                    "For wait: how long to block for the key to appear "
                    "(default 60, max 300)."
                ),
            },
            "value": {
                "type": "string",
                "description": (
                    "Entry value for post. Plain text or a JSON document as a "
                    "string (parsed and stored structurally when valid JSON)."
                ),
            },
            "author": {
                "type": "string",
                "description": (
                    "Who is posting (e.g. 'parent', 'worker:research'). Helps "
                    "readers attribute entries; defaults to 'agent'. For claim "
                    "and release this identifies the lease holder, so use a "
                    "stable id that is distinct from your siblings'."
                ),
            },
            "board": {
                "type": "string",
                "description": "Board id. Omit to use the shared session board.",
            },
        },
        "required": ["action"],
    },
}


registry.register(
    name="blackboard",
    toolset="blackboard",
    schema=BLACKBOARD_SCHEMA,
    handler=lambda args, **kw: blackboard_tool(
        action=args.get("action", ""),
        key=args.get("key", ""),
        value=args.get("value", ""),
        author=args.get("author", ""),
        board=args.get("board", ""),
        timeout_seconds=args.get("timeout_seconds", 60.0),
        ttl_seconds=args.get("ttl_seconds", _DEFAULT_CLAIM_TTL),
        min_support=args.get("min_support", 0),
    ),
    check_fn=lambda: True,
    emoji="📋",
)
