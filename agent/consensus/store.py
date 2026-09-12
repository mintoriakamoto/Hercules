"""Durable home for identity and evidence.

:class:`~agent.consensus.records.EvidenceLog` keeps its chain in memory, which
is fine for a unit test and useless for the thing it exists to support: rank
has to accumulate across runs, and a log that dies with the process means
every agent starts from zero forever. Likewise :class:`Identity` can be
restored from a seed, but nothing persisted one, so an "agent id" lasted
exactly as long as the interpreter.

This module stores both under ``~/.hercules/consensus``: the seed in a
mode-600 file, the record chain in SQLite. The chain invariant survives the
round trip — records come back in order, ``prev`` still points at the record
before, and every signature is re-checkable, so a log read from disk is
exactly as trustworthy as one built in memory. Tampering with the database
does not help an attacker: altering a record breaks its signature, and
removing or reordering one breaks the prev-link of everything after it.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Iterator, Optional

from agent.consensus.identity import Identity
from agent.consensus.records import SignedRecord

_ENV_HOME = "HERCULES_CONSENSUS_HOME"
_SEED_FILENAME = "identity.seed"
_DB_FILENAME = "evidence.db"

_init_lock = threading.Lock()
_initialized: set[str] = set()


def consensus_home() -> Path:
    """Directory holding this installation's consensus state."""
    override = os.environ.get(_ENV_HOME)
    if override:
        return Path(override)
    from hercules_constants import get_hercules_home

    return get_hercules_home() / "consensus"


def load_or_create_identity() -> Identity:
    """This installation's durable identity, generated once and reused.

    The seed is the private key: it is written 0600 into a 0700 directory and
    must never be logged or copied into a record body.
    """
    home = consensus_home()
    home.mkdir(parents=True, exist_ok=True)
    try:
        home.chmod(0o700)
    except OSError:
        pass
    seed_path = home / _SEED_FILENAME

    if seed_path.exists():
        seed = seed_path.read_bytes()
        if len(seed) == 32:
            return Identity.from_seed(seed)
        raise ValueError(
            f"{seed_path} is {len(seed)} bytes, not a 32-byte Ed25519 seed. "
            "Refusing to guess — move it aside to mint a new identity, "
            "understanding that this agent's accumulated standing is tied to "
            "the old key."
        )

    identity = Identity.generate()
    # Create with the right mode from the start rather than chmod-ing after:
    # otherwise the seed is briefly world-readable on disk.
    fd = os.open(seed_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, identity.seed())
    finally:
        os.close(fd)
    return identity


def _db_path() -> Path:
    return consensus_home() / _DB_FILENAME


def _connect() -> sqlite3.Connection:
    path = _db_path()
    key = str(path)
    if key not in _initialized:
        with _init_lock:
            if key not in _initialized:
                path.parent.mkdir(parents=True, exist_ok=True)
                init = sqlite3.connect(path, timeout=10.0)
                try:
                    init.execute("PRAGMA journal_mode=WAL")
                    init.execute(
                        "CREATE TABLE IF NOT EXISTS evidence ("
                        " seq INTEGER PRIMARY KEY AUTOINCREMENT,"
                        " hash TEXT NOT NULL UNIQUE,"
                        " prev TEXT,"
                        " record TEXT NOT NULL)"
                    )
                    init.commit()
                finally:
                    init.close()
                _initialized.add(key)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


class PersistentEvidenceLog:
    """An append-only hash-linked record chain backed by SQLite.

    Same contract as :class:`~agent.consensus.records.EvidenceLog` — append
    refuses a bad signature or a ``prev`` that does not point at the current
    head — except the chain outlives the process.
    """

    def __init__(self, *, connection_factory=_connect) -> None:
        self._connect = connection_factory

    @property
    def head(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT hash FROM evidence ORDER BY seq DESC LIMIT 1"
            ).fetchone()
        return row[0] if row else None

    def append(self, record: SignedRecord) -> None:
        if not record.verify():
            raise ValueError("record signature is invalid")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT hash FROM evidence ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            head = row[0] if row else None
            if record.prev != head:
                raise ValueError(
                    f"prev-hash mismatch: record.prev={record.prev!r} head={head!r}"
                )
            # UNIQUE(hash) is the backstop against a double append racing the
            # head read above: the second writer loses instead of forking.
            conn.execute(
                "INSERT INTO evidence (hash, prev, record) VALUES (?, ?, ?)",
                (
                    record.hash,
                    record.prev,
                    json.dumps(record.to_dict(), sort_keys=True, ensure_ascii=False),
                ),
            )

    def records(self) -> list[SignedRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT record FROM evidence ORDER BY seq"
            ).fetchall()
        return [SignedRecord.from_dict(json.loads(raw)) for (raw,) in rows]

    def records_of_kind(self, kind: str) -> list[SignedRecord]:
        return [r for r in self.records() if r.kind == kind]

    def verify_chain(self) -> bool:
        """Re-check every signature and prev-link from genesis to head."""
        prev = None
        for record in self.records():
            if not record.verify() or record.prev != prev:
                return False
            prev = record.hash
        return True

    def __len__(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()
        return int(row[0]) if row else 0

    def __iter__(self) -> Iterator[SignedRecord]:
        return iter(self.records())
