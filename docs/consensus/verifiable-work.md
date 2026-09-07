# Can Hercules agents run on a decentralized blockchain?

Short answer: **most of the primitives are already here, and a blockchain
deliberately isn't one of them.** That call was made in
[`web-of-trust.md`](web-of-trust.md) and implemented in `agent/consensus/`. This
note picks up where that one stops — at the sentence *"wiring it into the agent
loop and choosing a gossip transport are the next steps"* — and works out what
those next steps actually require.

## What already exists

| Piece | Where | State |
|---|---|---|
| Agent identity = Ed25519 keypair, `agent_id` **is** the public key | `agent/consensus/identity.py` | Built, tested |
| Signed, hash-linked `claim` / `validation` records | `agent/consensus/records.py` | Built, tested |
| Append-only `EvidenceLog` refusing bad signatures or broken `prev` links | `agent/consensus/records.py:176` | Built, in-memory only |
| Web-of-trust reputation relative to a chosen root | `agent/consensus/trust.py` | Built, tested |
| Passive ledger of which checks an agent actually ran and their exit status | `agent/verification_evidence.py` | Built, unconnected to the above |

The rationale for signatures-and-hashes over mining is in `web-of-trust.md` and
still holds: you cannot mine correctness, and the threat model here is Sybil,
not double-spend.

## The actual gap

`claim` carries a `solution_hash`. `validation` carries a `verdict` in
`[-1, 1]`. **Nothing in the codebase says how a peer computes that verdict.**

That is the keystone, and it is a harder problem than the ledger. A decentralized
network can only reach agreement about work when *verifying* is substantially
cheaper than *producing* — the asymmetry is what makes peer review affordable
rather than a re-run of the whole job by everyone.

## Verification tiers

Agent work does not divide evenly along that asymmetry. Three tiers, and only
the first two support anything resembling objective consensus:

### Tier 1 — Mechanically checkable

Test suite passes, build succeeds, benchmark reproduces, script exits 0.
Verification is re-execution in the same environment and comparison of exit
status. This is exactly what `agent/verification_evidence.py` already records —
classified command results, deliberately passive.

**Blocker:** re-execution has to be reproducible, and it currently isn't.
`tools/environments/docker.py` inspects images for entrypoint type but does not
pin an image *digest*, and no seed control exists anywhere. Two nodes running
"the same" task today are not running the same task.

### Tier 2 — Cheap to check, expensive to find

Formal proofs (the checker is trivial, the search is not), optimization results
(evaluate the objective function), constraint satisfaction, "find an input that
triggers this bug". This is the genuine sweet spot — real asymmetry, no
environment reproduction needed, verification is a pure function of the claim.

If the "agents mine verified solutions" framing is going to mean anything
concrete, **this tier is where it lives.**

### Tier 3 — Judgment-dependent

"Is this essay good", "is this refactor cleaner", "did it understand the
request". No cheap oracle exists. Verification collapses into correlated
opinion.

Worth saying plainly: **most agent work is Tier 3.** A design that quietly
assumes otherwise will look rigorous and mean nothing. The honest handling is
what `trust.py` already does — degrade to reputation relative to a trust root,
and don't pretend the result is objective.

## How the pieces would connect

```
agent completes task
        │
        ├─ verification_evidence records: which checks ran, exit status
        │
        ▼
    claim(problem, solution_hash, stake)          ← signed, Ed25519
        │   body extended with: evidence digest + environment digest
        ▼
    peer re-executes (Tier 1) or re-checks (Tier 2)
        │
        ▼
    validation(claim_hash, verdict)               ← signed
        │
        ▼
    TrustGraph.reputation(root, agent) updates
```

The claim body would need two fields it does not have today: a digest of the
verification evidence, and a digest of the environment the evidence was produced
in. Both are additive — `SignedRecord.body` is a free-form dict, so this needs no
change to the record format or the signing scheme.

## What is genuinely missing

Concrete, in rough dependency order:

1. **Environment pinning.** Image digests in the Docker backend. Without it Tier 1
   verification is unsound. Smallest, most valuable piece.
2. **Evidence → claim binding.** A function turning a `verification_evidence`
   session into the digest a claim commits to.
3. **`EvidenceLog` persistence.** It is in-memory; nothing survives a restart.
   SQLite alongside the existing `hercules_state.py` store is the obvious fit.
4. **Transport.** Nothing networked exists at all.
5. **Stake accounting.** `-1` refutes and "slashes", but no balance is tracked.

## Transport options

`web-of-trust.md` calls transport pluggable and out of scope. The realistic
candidates, with honest costs:

| Option | Cost | Notes |
|---|---|---|
| **Git repository as the log** | Zero new dependencies | Records are already hash-linked and signed; a repo is an append-only log with sync built in. Federated rather than P2P. Easiest to test. |
| **Nostr relays** | One small client dep | Relays already carry signed events keyed by pubkey, which matches `agent_id` exactly. Existing public relay infrastructure. |
| **libp2p / gossipsub** | Heavy dependency, real P2P | Correct end state if the network gets large; premature now. |

Recommendation: **git first.** It is testable today with no new dependencies and
exercises the whole claim/validation/reputation path end to end. Swapping in
nostr later changes only the transport seam.

## On tokens and stake

Stake only deters false claims if it is costly to acquire. Three ways to make it
so, and this is a product decision rather than a technical one:

- **Reputation-only stake** — a refuted claim costs standing in the trust graph.
  Free, no regulatory surface, and weaker: a fresh keypair costs nothing, though
  web-of-trust already gives a fresh key a reputation of zero.
- **External bond** — stake denominated in something that already exists.
- **Native token** — strongest economic guarantee, and it brings a regulatory and
  complexity burden that would likely dominate the project.

The existing design gets meaningful Sybil resistance *without* any of these,
because reputation is relative to a trust root and unreachable agents score zero.
A token would add economic finality to Tier 1/Tier 2 claims. It would add nothing
to Tier 3.

## Open questions

These need answers before any of the above is worth building:

1. **Which tier is the target?** Tier 2 makes "mine verified solutions" literal
   and real, but narrows Hercules to problems with cheap checkers. Tier 1
   generalizes further but needs reproducible environments first. Tier 3 cannot
   be made objective at all.
2. **Who are the peers?** Agents belonging to one operator (then trust is
   trivial and the ledger is mostly an audit log), or mutually untrusting parties
   (then everything above matters)?
3. **Is stake economic or reputational?** Determines whether a token enters the
   picture at all.

## Status

This document is design analysis, not an implementation plan with dates. Nothing
described under "What is genuinely missing" has been built. The existing
`agent/consensus/` module is real, tested, and unwired — it does not talk to a
network and is not called from the agent loop.
