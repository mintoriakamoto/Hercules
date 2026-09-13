"""Decentralized consensus primitives for Hercules — a web of trust.

The repo's premise is that agents earn rank by having their solutions verified
by peers. This package implements that with the smallest honest primitive:

* :mod:`~agent.consensus.identity`  — an agent *is* an Ed25519 key.
* :mod:`~agent.consensus.records`   — signed, hash-linked claims and
  validations (tamper-evident "immutable evidence").
* :mod:`~agent.consensus.trust`     — reputation by web-of-trust distance from
  a chosen root; Sybil-resistant, no proof-of-work.
* :mod:`~agent.consensus.store`     — durable identity and a SQLite-backed
  record chain, so standing accumulates across runs instead of dying with the
  process.
* :mod:`~agent.consensus.standing`  — settled claims become rank and compute,
  with decay and a reserved slice so position is re-earned and no agent can
  corner the pool.
* :mod:`~agent.consensus.proofs`    — claims that commit to a replayable
  proof, so standing is earned by re-running the check rather than by peers
  voting on it. A ``validation`` is an opinion; a ``verification`` is evidence.

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
from agent.consensus.proofs import (
    VERIFICATION,
    VERIFIED_CLAIM,
    Observation,
    Proof,
    ProofRunner,
    derive_verdict,
    independent_verdicts,
    is_self_consistent,
    make_runner,
    output_hash,
    proof_of,
    replay,
    settle,
    stake_at_risk,
    verdict_of,
    verification,
    verified_claim,
)
from agent.consensus.standing import (
    Standing,
    compute_allocation,
    may_validate,
    ranked,
    standings,
)
from agent.consensus.store import (
    PersistentEvidenceLog,
    consensus_home,
    load_or_create_identity,
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
    "Proof",
    "Observation",
    "ProofRunner",
    "verified_claim",
    "verification",
    "replay",
    "derive_verdict",
    "verdict_of",
    "proof_of",
    "is_self_consistent",
    "independent_verdicts",
    "settle",
    "stake_at_risk",
    "output_hash",
    "make_runner",
    "VERIFIED_CLAIM",
    "VERIFICATION",
    "PersistentEvidenceLog",
    "load_or_create_identity",
    "consensus_home",
    "Standing",
    "standings",
    "ranked",
    "compute_allocation",
    "may_validate",
]
