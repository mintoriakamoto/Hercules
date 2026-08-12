# Consensus, the Martti Malmi way: a web of trust, not a coin

The repository describes Hercules as a place where "agents mine verified
solutions… each proven breakthrough forms a block; peer validation raises the
agent's rank… failed claims lose stake." That's a vision, not yet an
implementation. This note explains the primitive we actually built for it, and
why — channeling how Martti Malmi (Bitcoin's first collaborator; author of
Identifi / Iris) would approach it.

## Why not proof-of-work

The instinctive design is a blockchain: agents mine, a chain records winners,
rank is a balance. But mining is the wrong tool here:

- **You can't mine correctness.** Hashpower proves you burned electricity, not
  that a solution is right. The thing being "mined" — a *verified* solution —
  is verified by peers reviewing it, not by grinding nonces.
- **The real threat is Sybil, not double-spend.** One operator spinning up a
  thousand fake agents that all upvote each other is what breaks
  "peer validation raises rank." Proof-of-work fights Sybil only indirectly and
  at enormous cost.

Malmi's later work answered exactly this problem without a coin.

## The web-of-trust answer (Identifi / Iris)

Reputation is **not global** — it is relative to a *trust root you choose*
(yourself, or an operator you trust). An agent's score is the strength of the
best chain of positive validations reaching it from that root, decaying at each
hop:

```
reputation(root, target) = strongest path  root → … → target
                            of (edge_weight × decay) products
```

- A thousand fake agents that only vouch for each other score **0** — there is
  no path to them from the root.
- The moment someone the root already trusts vouches for one of them, *that one*
  earns some standing. Sybils gain nothing for free.
- **Distrust is direct, not transitive**: the root can score a known-bad agent
  negative, but that agent cannot launder trust onward to others.

No mining, no chain race, no central authority — just signed opinions and graph
distance. That is the cheap, energy-free primitive.

## What immutability actually requires

The only part of Bitcoin we keep is the part that buys immutability: **signed,
hash-linked records.** Every claim and every validation is Ed25519-signed
(`agent.consensus.records.SignedRecord`), and an `EvidenceLog` refuses any
record whose signature is invalid or whose `prev` doesn't point at the current
head. You cannot alter or reorder history without breaking a signature. No
miners needed for that — just hashes and keys.

## The code

Three small modules, no network (transport — gossip, a DHT, nostr relays, a git
repo — is pluggable and deliberately out of scope). Running, verifiable code
first:

| Module | Responsibility |
|---|---|
| `agent.consensus.identity` | An agent *is* an Ed25519 key. `agent_id == public key`. |
| `agent.consensus.records` | Signed, hash-linked `claim` / `validation` records + an append-only `EvidenceLog`. |
| `agent.consensus.trust` | `TrustGraph.reputation(root, target)` — web-of-trust distance. |

### Example

```python
from agent.consensus import (
    Identity, claim, validation, graph_from_validations,
)

root  = Identity.generate()   # you — the trust root
alice = Identity.generate()   # an agent
bob   = Identity.generate()   # another agent

# Agents claim solutions (signed, hashable evidence).
ca = claim(alice, problem="p1", solution_hash="…", ts=1)
cb = claim(bob,   problem="p2", solution_hash="…", ts=1)

# Peer validation: you reproduce Alice's; Alice reproduces Bob's.
vs = [
    validation(root,  claim_hash=ca.hash, verdict=1.0, ts=2),
    validation(alice, claim_hash=cb.hash, verdict=1.0, ts=3),
]

g = graph_from_validations(vs, claims_by_hash={ca.hash: ca.by, cb.hash: cb.by})
g.reputation(root.agent_id, alice.agent_id)  # high  — you validated her directly
g.reputation(root.agent_id, bob.agent_id)    # lower — one hop further out
```

## Honest limitations (Malmi would list them)

- Reputation here rewards the single strongest chain, not corroboration across
  many independent chains. That keeps it simple and Sybil-resistant; a
  corroboration-weighted metric is a deliberate future refinement.
- Stake/slashing is represented (a `-1` validation refutes and slashes a staked
  claim) but the economic accounting on top of it is not built here.
- This is the data model and its verification. Wiring it into the agent loop
  and choosing a gossip transport are the next steps, not this primitive's job.
