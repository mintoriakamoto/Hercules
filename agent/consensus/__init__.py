"""Decentralized consensus primitives for Hercules — a web of trust.

The repo's premise is that agents earn rank by having their solutions verified
by peers. This package implements that with the smallest honest primitive:

* :mod:`~agent.consensus.identity`  — an agent *is* an Ed25519 key.
* :mod:`~agent.consensus.records`   — signed, hash-linked claims and
  validations (tamper-evident "immutable evidence").
* :mod:`~agent.consensus.trust`     — reputation by web-of-trust distance from
  a chosen root; Sybil-resistant, no proof-of-work.

Nothing here talks to a network. The data model and its verification are the
substance; transport (gossip, a DHT, nostr relays, a git repo) is pluggable and
deliberately out of scope. Running, verifiable code first.
"""

from agent.consensus.identity import Identity, b64decode, b64encode, verify
from agent.consensus.records import (
    CLAIM,
    VALIDATION,
    EvidenceLog,
    SignedRecord,
    canonical_bytes,
    claim,
    content_hash,
    validation,
)
from agent.consensus.trust import TrustGraph, graph_from_validations

__all__ = [
    "Identity",
    "verify",
    "b64encode",
    "b64decode",
    "SignedRecord",
    "EvidenceLog",
    "claim",
    "validation",
    "canonical_bytes",
    "content_hash",
    "CLAIM",
    "VALIDATION",
    "TrustGraph",
    "graph_from_validations",
]
