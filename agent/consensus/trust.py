"""Web of trust — reputation without proof-of-work.

The repo's pitch is that "peer validation raises an agent's rank." The naive
reading is a coin: agents mine, a chain records winners. But you cannot mine a
*verified solution* with hashpower, and burning energy proves nothing about
whether an answer is correct. The Sybil problem — one attacker spinning up a
thousand fake agents who all vouch for each other — is the real threat, and
proof-of-work is a very expensive, indirect defense against it.

The cheaper, energy-free answer is a **web of trust** (the Identifi / Iris
model): reputation is not global, it is *relative to a trust root you choose*.
An agent's score is the strength of the best chain of positive validations
reaching it from that root, decaying at each hop. A thousand fake agents who
only vouch for each other score zero — there is no path to them from the root.
The moment someone the root already trusts vouches for one, that one (and only
that one) earns some standing. No mining, no chain race, no central authority:
just signed opinions and graph distance.

This module computes reputation over the validation graph. Building that graph
from signed ``validation`` records (so the edges are authenticated) is the
caller's job; see :func:`graph_from_validations`.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Optional

# A directed edge ``a -> b`` means "a has, on balance, positively validated b".
# Its weight is in [-1, 1]. Negative weight is distrust and, deliberately, does
# NOT propagate onward (see reputation()).
DEFAULT_MAX_DEPTH = 6
DEFAULT_DECAY = 0.5


class TrustGraph:
    """A directed, weighted trust graph with a best-path reputation metric."""

    def __init__(self) -> None:
        # src -> {dst -> [weights]}. Multiple opinions from the same source
        # about the same target are averaged when the edge is read.
        self._opinions: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def add_opinion(self, src: str, dst: str, weight: float) -> None:
        """Record that *src* rated *dst* with *weight* in [-1, 1].

        Self-edges are ignored — you cannot vouch for yourself.
        """
        if src == dst:
            return
        self._opinions[src][dst].append(max(-1.0, min(1.0, float(weight))))

    def edge_weight(self, src: str, dst: str) -> Optional[float]:
        """Aggregate weight of *src*'s opinions about *dst* (mean), or None."""
        weights = self._opinions.get(src, {}).get(dst)
        if not weights:
            return None
        return sum(weights) / len(weights)

    def _out_edges(self, src: str) -> dict[str, float]:
        return {
            dst: (sum(ws) / len(ws))
            for dst, ws in self._opinions.get(src, {}).items()
            if ws
        }

    def reputation(
        self,
        root: str,
        target: str,
        *,
        max_depth: int = DEFAULT_MAX_DEPTH,
        decay: float = DEFAULT_DECAY,
    ) -> float:
        """Reputation of *target* as seen from *root*, in [-1, 1].

        Computed as the strongest trusted path: trust starts at 1.0 at *root*
        and, along each hop, is multiplied by the edge weight and by *decay*.
        Only positive trust propagates onward, so distrust is a *direct* signal
        (it can lower a target the root reaches negatively) but is never
        transitively laundered through a distrusted node. ``root`` itself is
        1.0; an unreachable target is 0.0.

        Trade-off, stated honestly: this rewards the single most-trusting chain
        rather than corroboration across many independent chains. That keeps it
        simple and Sybil-resistant; a corroboration-weighted metric is a
        deliberate future refinement, not an accident.
        """
        if target == root:
            return 1.0
        if not 0.0 < decay <= 1.0:
            raise ValueError("decay must be in (0, 1]")

        best: dict[str, float] = {root: 1.0}
        frontier = {root}
        for _ in range(max_depth):
            improved: set[str] = set()
            for node in frontier:
                node_trust = best[node]
                if node_trust <= 0.0:
                    # Unknown or distrusted nodes do not pass trust along.
                    continue
                for nxt, weight in self._out_edges(node).items():
                    candidate = node_trust * weight * decay
                    if candidate > best.get(nxt, float("-inf")):
                        best[nxt] = candidate
                        improved.add(nxt)
            if not improved:
                break
            frontier = improved

        return max(-1.0, min(1.0, best.get(target, 0.0)))

    def ranking(
        self,
        root: str,
        *,
        max_depth: int = DEFAULT_MAX_DEPTH,
        decay: float = DEFAULT_DECAY,
    ) -> list[tuple[str, float]]:
        """All agents the *root* can reach, sorted by reputation (desc).

        Excludes the root itself. Agents with exactly 0.0 (unreachable) are
        omitted; negatively-scored agents are included so callers can see who
        the root distrusts.
        """
        seen: set[str] = set()
        for src, dsts in self._opinions.items():
            seen.add(src)
            seen.update(dsts)
        scored = [
            (agent, self.reputation(root, agent, max_depth=max_depth, decay=decay))
            for agent in seen
            if agent != root
        ]
        scored = [(a, s) for a, s in scored if s != 0.0]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored


def graph_from_validations(
    validations: Iterable, claims_by_hash: Optional[dict] = None
) -> TrustGraph:
    """Build a :class:`TrustGraph` from signed ``validation`` records.

    Each validation edge runs from the validator (``record.by``) to the *author
    of the claim it reviews*, weighted by the verdict. Only records that verify
    and that resolve to a known claim author are used, so the graph is built
    from authenticated opinions — a forged or unsigned validation contributes
    nothing.

    ``claims_by_hash`` maps a claim's hash to its author agent id (typically
    ``{c.hash: c.by for c in claims}``). When omitted, validations that carry a
    ``target`` agent id directly in their body are used instead.
    """
    graph = TrustGraph()
    claims_by_hash = claims_by_hash or {}
    for record in validations:
        if getattr(record, "kind", None) != "validation" or not record.verify():
            continue
        body = record.body
        claim_hash = body.get("claim_hash")
        target = claims_by_hash.get(claim_hash) or body.get("target")
        if not target:
            continue
        graph.add_opinion(record.by, target, body.get("verdict", 0.0))
    return graph
