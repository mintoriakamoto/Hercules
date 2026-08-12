"""Signed, hash-linked records — the "immutable evidence" layer.

Every claim an agent makes and every peer validation is a signed record. In a
log, each record commits to the hash of the one before it, so the history is
tamper-evident: you cannot alter or reorder a past record without breaking the
hash chain — and every signature is independently checkable besides. No
blockchain, no miners, no proof-of-work: just signatures and hashes, which is
the part of Bitcoin that actually buys you immutability.

Two record kinds carry the system:

* ``claim``      — an agent claims it solved problem ``P`` with solution
                   ``solution_hash``, optionally staking ``stake``.
* ``validation`` — an agent peer-reviews a claim (by its hash) with a
                   ``verdict`` in [-1, 1]: +1 reproduced/correct, -1 refuted
                   (which is also what slashes a staked claim).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from agent.consensus.identity import Identity, verify

CLAIM = "claim"
VALIDATION = "validation"


def canonical_bytes(obj: Any) -> bytes:
    """Deterministic JSON encoding used for hashing and signing.

    Sorted keys + compact separators mean the same logical content always
    produces the same bytes, so a signature made on one machine verifies on
    any other.
    """
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def content_hash(obj: Any) -> str:
    """SHA-256 (hex) of the canonical encoding of *obj*."""
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


@dataclass(frozen=True)
class SignedRecord:
    """An immutable, signed record, optionally chained to a prior record.

    The signature covers everything but the signature itself and the cached
    hash, so the record's authenticity and its link to history are both
    verifiable by anyone, offline.
    """

    kind: str
    by: str  # author agent id
    ts: int  # author-supplied timestamp (seconds); kept in the signed payload
    body: dict = field(default_factory=dict)
    prev: Optional[str] = None  # hash of the previous record in a log, or None
    sig: str = ""

    def _payload(self) -> dict:
        """The signed portion — everything except the signature."""
        return {
            "kind": self.kind,
            "by": self.by,
            "ts": self.ts,
            "body": self.body,
            "prev": self.prev,
        }

    @property
    def hash(self) -> str:
        """Stable content hash of the signed payload (id of this record)."""
        return content_hash(self._payload())

    def verify(self) -> bool:
        """True iff the signature is a valid signature of the payload by ``by``."""
        if not self.sig:
            return False
        return verify(self.by, canonical_bytes(self._payload()), self.sig)

    @classmethod
    def create(
        cls,
        identity: Identity,
        kind: str,
        body: dict,
        *,
        ts: int,
        prev: Optional[str] = None,
    ) -> "SignedRecord":
        """Build and sign a record authored by *identity*."""
        payload = {
            "kind": kind,
            "by": identity.agent_id,
            "ts": int(ts),
            "body": body,
            "prev": prev,
        }
        sig = identity.sign(canonical_bytes(payload))
        return cls(
            kind=kind,
            by=identity.agent_id,
            ts=int(ts),
            body=body,
            prev=prev,
            sig=sig,
        )

    def to_dict(self) -> dict:
        return {**self._payload(), "sig": self.sig}

    @classmethod
    def from_dict(cls, data: dict) -> "SignedRecord":
        return cls(
            kind=data["kind"],
            by=data["by"],
            ts=int(data["ts"]),
            body=dict(data.get("body") or {}),
            prev=data.get("prev"),
            sig=data.get("sig", ""),
        )


def claim(
    identity: Identity,
    *,
    problem: str,
    solution_hash: str,
    ts: int,
    stake: float = 0.0,
    prev: Optional[str] = None,
) -> SignedRecord:
    """A signed claim that *identity* solved *problem* with *solution_hash*."""
    return SignedRecord.create(
        identity,
        CLAIM,
        {
            "problem": problem,
            "solution_hash": solution_hash,
            "stake": float(stake),
        },
        ts=ts,
        prev=prev,
    )


def validation(
    identity: Identity,
    *,
    claim_hash: str,
    verdict: float,
    ts: int,
    reason: str = "",
    prev: Optional[str] = None,
) -> SignedRecord:
    """A signed peer-review of a claim.

    ``verdict`` is clamped to [-1, 1]: +1 = reproduced/correct, 0 = abstain,
    -1 = refuted (slashes a staked claim). ``reason`` is free text.
    """
    v = max(-1.0, min(1.0, float(verdict)))
    return SignedRecord.create(
        identity,
        VALIDATION,
        {"claim_hash": claim_hash, "verdict": v, "reason": reason},
        ts=ts,
        prev=prev,
    )


class EvidenceLog:
    """An append-only, hash-linked, signature-checked sequence of records.

    ``append`` refuses any record whose signature is invalid or whose ``prev``
    does not point at the current head, so the log can only ever grow forward
    and can be re-verified end to end at any time with :meth:`verify_chain`.
    """

    def __init__(self) -> None:
        self._records: list[SignedRecord] = []

    @property
    def head(self) -> Optional[str]:
        """Hash of the most recent record, or ``None`` when empty."""
        return self._records[-1].hash if self._records else None

    def append(self, record: SignedRecord) -> None:
        if not record.verify():
            raise ValueError("record signature is invalid")
        if record.prev != self.head:
            raise ValueError(
                f"prev-hash mismatch: record.prev={record.prev!r} head={self.head!r}"
            )
        self._records.append(record)

    def verify_chain(self) -> bool:
        """Re-check every signature and every prev-link from genesis to head."""
        prev = None
        for record in self._records:
            if not record.verify() or record.prev != prev:
                return False
            prev = record.hash
        return True

    def records(self) -> list[SignedRecord]:
        return list(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self):
        return iter(self._records)
