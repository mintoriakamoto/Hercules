"""Standing — turning settled claims into position, carefully.

The reward in this system is not a coin, it is an elevated position: rank,
and the compute and scope that follow from it. That is a better reward than a
token and a more dangerous one. A coin is inert — an agent that games the
oracle and earns a million of them has a million coins and no new
capabilities. Position is capability-granting, so the payoff for beating the
system is a better seat from which to beat it. Two properties keep that loop
open rather than runaway, and both are enforced here rather than left to
whoever wires this up.

**Rank buys resources, never truth.** Nothing in this module is consulted when
a claim is verified. :func:`~agent.consensus.proofs.independent_verdicts`
takes no standing and weighs no reputations: one refutation from the lowest
agent in the system disqualifies a claim that every high-ranking agent
confirmed, because the proof is deterministic and a bloc out-voting a real
failure is exactly the corruption to prevent. Position may buy compute,
priority and scope. It must never buy influence over what counts as verified.

**Position decays.** Rank is a rolling measure of recent verified work, not a
balance. Without new verified claims an agent's standing falls off on a
half-life, so a seat has to be re-earned and an early winner cannot hold one
forever on the strength of one good week.

**Capacity is reserved.** Allocating compute purely in proportion to rank is
positive feedback and converges: the leader earns more compute, produces more
verified work, earns more compute. The end state is one dominant agent, which
is a monoculture, which is maximally correlated failure — and correlated
failure is precisely what independent verification exists to catch. So a
fraction of compute is distributed regardless of rank. That is not fairness,
it is the mechanism protecting the diversity the whole scheme rests on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from agent.consensus.proofs import VERIFIED_CLAIM, settle
from agent.consensus.records import SignedRecord

# Standing halves in a week of silence: long enough that a productive agent
# keeps its seat between sessions, short enough that one good run does not
# confer a permanent position.
DEFAULT_HALF_LIFE_SECONDS = 7 * 24 * 3600
# A fifth of compute ignores rank entirely. Enough that a new or unlucky agent
# can still produce the work that earns it a seat.
DEFAULT_RESERVED_FRACTION = 0.2


@dataclass(frozen=True)
class Standing:
    """An agent's earned position at a point in time."""

    agent_id: str
    rank: float
    compute_share: float
    verified: int
    refuted: int


def _decay(age_seconds: float, half_life_seconds: float) -> float:
    if half_life_seconds <= 0:
        return 1.0
    return 0.5 ** (max(0.0, age_seconds) / half_life_seconds)


def rank_contributions(
    claims: Iterable[SignedRecord],
    verifications: list[SignedRecord],
    *,
    now: int,
    half_life_seconds: float = DEFAULT_HALF_LIFE_SECONDS,
) -> dict[str, dict]:
    """Per-agent verified/refuted counts and decayed rank.

    A verified claim credits ``1 + stake``; a refutation debits the same. Stake
    amplifies both directions, which is the entire point of staking: an agent
    that wants more credit for a claim must risk more on it being wrong.

    An *unproven* claim moves nothing. Work nobody replayed has earned nothing,
    and that is not the same as having failed.
    """
    tallies: dict[str, dict] = {}
    for claim in claims:
        if claim.kind != VERIFIED_CLAIM:
            continue
        outcome = settle(claim, verifications)
        entry = tallies.setdefault(
            claim.by, {"rank": 0.0, "verified": 0, "refuted": 0}
        )
        if outcome["outcome"] == "unproven":
            continue
        weight = (1.0 + abs(float(claim.body.get("stake", 0.0)))) * _decay(
            now - claim.ts, half_life_seconds
        )
        if outcome["outcome"] == "verified":
            entry["rank"] += weight
            entry["verified"] += 1
        else:
            entry["rank"] -= weight
            entry["refuted"] += 1
    return tallies


def standings(
    claims: Iterable[SignedRecord],
    verifications: list[SignedRecord],
    *,
    now: int,
    half_life_seconds: float = DEFAULT_HALF_LIFE_SECONDS,
    reserved_fraction: float = DEFAULT_RESERVED_FRACTION,
) -> dict[str, Standing]:
    """Standing for every agent that has made a claim.

    ``compute_share`` values sum to 1.0 across participants: a reserved slice
    split evenly regardless of rank, and the remainder in proportion to rank.
    An agent whose rank has gone negative through refutations still receives
    its reserved slice — starving it entirely would remove it from the pool
    permanently on the strength of past failures, and an agent that cannot
    work can never demonstrate that it has improved.
    """
    reserved = min(max(float(reserved_fraction), 0.0), 1.0)
    tallies = rank_contributions(
        claims, verifications, now=now, half_life_seconds=half_life_seconds
    )
    if not tallies:
        return {}

    # Only positive rank competes for the merit slice; a negative rank earns
    # no share of it, but is not pushed below zero into a debt that would take
    # an agent several good claims just to return to neutral.
    positive = {a: max(0.0, t["rank"]) for a, t in tallies.items()}
    total_positive = sum(positive.values())
    even_slice = reserved / len(tallies)

    result: dict[str, Standing] = {}
    for agent_id, tally in tallies.items():
        if total_positive > 0:
            merit = (1.0 - reserved) * (positive[agent_id] / total_positive)
        else:
            # Nobody has positive rank yet: share the whole pool evenly rather
            # than allocating nothing to anyone.
            merit = (1.0 - reserved) / len(tallies)
        result[agent_id] = Standing(
            agent_id=agent_id,
            rank=round(tally["rank"], 6),
            # Not rounded: this is a ratio that feeds compute_allocation, and
            # rounding each share for cosmetics stops them summing to 1.
            compute_share=even_slice + merit,
            verified=tally["verified"],
            refuted=tally["refuted"],
        )
    return result


def ranked(standings_by_agent: dict[str, Standing]) -> list[Standing]:
    """Standings ordered best first, ties broken by agent id for determinism."""
    return sorted(
        standings_by_agent.values(), key=lambda s: (-s.rank, s.agent_id)
    )


def compute_allocation(
    standings_by_agent: dict[str, Standing], total_units: float
) -> dict[str, float]:
    """Split ``total_units`` of compute across agents by their share."""
    return {
        agent_id: round(s.compute_share * float(total_units), 6)
        for agent_id, s in standings_by_agent.items()
    }


def may_validate(claim: SignedRecord, verifier_id: str) -> bool:
    """Whether *verifier_id* is allowed to verify *claim*.

    Deliberately takes no standing argument. Rank is not an input to this
    decision and must never become one — the only disqualification is
    authorship, because an agent grading its own homework mints rank from
    nothing.
    """
    return claim.by != verifier_id


def reserved_floor(
    standings_by_agent: dict[str, Standing],
    reserved_fraction: float = DEFAULT_RESERVED_FRACTION,
) -> float:
    """The compute share every participant receives regardless of rank."""
    if not standings_by_agent:
        return 0.0
    return reserved_fraction / len(standings_by_agent)
