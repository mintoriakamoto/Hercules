"""Replayable proofs — the difference between verified work and peer opinion.

``records.validation`` lets a peer attach a verdict in [-1, 1] and some prose to
a claim. That is a vote. Nothing in it says *how* the claim was checked, and
nobody downstream can re-run the check, so a claim's standing rests on who
bothered to look and what they felt. Rank built on that is rank built on
opinion.

This module supplies the missing half. A claim carries a :class:`Proof` — a
command plus the outcome it must produce — inside the *signed* body, so the
bar is fixed at claim time and the claimant cannot move it afterwards. A peer
replays that command and signs what it *observed*. The verdict is then
**derived** by comparing observation against expectation, never asserted by the
verifier. Two agents replaying the same proof reach the same verdict or one of
them is lying, and either way the disagreement is visible.

That is what makes the work minable: expensive to produce, cheap to check, and
checkable by anyone, later, without trusting the checker.

Two invariants are enforced here rather than left to callers:

* **The claimant is never its own oracle.** :func:`verification` refuses to
  sign a verification of a claim the same identity authored. An agent that can
  grade its own homework earns rank for free, and rank that buys influence over
  what counts as verified corrupts every later claim.
* **This module never executes anything.** A proof command is authored by the
  agent making the claim — it is untrusted input, and replaying it is exactly
  the moment an attacker would choose to run something. :func:`replay` takes
  the runner as an argument so the caller decides what sandbox it lands in.
  Nothing here shells out, and nothing here should ever start.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from agent.consensus.identity import Identity
from agent.consensus.records import SignedRecord, content_hash

VERIFIED_CLAIM = "verified_claim"
VERIFICATION = "verification"


@dataclass(frozen=True)
class Proof:
    """A machine-checkable bar for a claim: run ``command``, expect this.

    ``expect_exit`` alone is enough for the common case (a test suite, a
    typechecker, a build). ``expect_output_hash`` additionally pins the output,
    for claims where exiting zero is not the whole story — a benchmark that
    must produce a specific result, say.
    """

    command: str
    expect_exit: int = 0
    expect_output_hash: Optional[str] = None

    def to_body(self) -> dict:
        return {
            "command": self.command,
            "expect_exit": int(self.expect_exit),
            "expect_output_hash": self.expect_output_hash,
        }

    @classmethod
    def from_body(cls, body: dict) -> "Proof":
        return cls(
            command=body["command"],
            expect_exit=int(body.get("expect_exit", 0)),
            expect_output_hash=body.get("expect_output_hash"),
        )

    def is_met(self, observed: "Observation") -> bool:
        """Did this run clear the bar? Purely mechanical, no identity needed.

        Kept on the Proof rather than only behind a signed record so callers
        with no key material -- delegation subagents, which are ephemeral and
        anonymous -- can still check work against a declared bar.
        """
        if observed.exit_code != self.expect_exit:
            return False
        if (
            self.expect_output_hash is not None
            and observed.output_hash != self.expect_output_hash
        ):
            return False
        return True


@dataclass(frozen=True)
class Observation:
    """What actually happened when a proof was replayed."""

    exit_code: int
    output_hash: Optional[str] = None

    def to_body(self) -> dict:
        return {
            "exit_code": int(self.exit_code),
            "output_hash": self.output_hash,
        }

    @classmethod
    def from_body(cls, body: dict) -> "Observation":
        return cls(
            exit_code=int(body["exit_code"]),
            output_hash=body.get("output_hash"),
        )


class ProofRunner(Protocol):
    """Executes a proof command and reports what happened.

    Implementations are responsible for isolation. The command came from
    another agent; treat it as hostile.
    """

    def __call__(self, command: str) -> Observation: ...


def output_hash(output: bytes | str) -> str:
    """Hash of proof output, for claims that pin more than an exit code."""
    raw = output.encode("utf-8") if isinstance(output, str) else output
    return content_hash({"output": raw.decode("utf-8", errors="replace")})


def verified_claim(
    identity: Identity,
    *,
    problem: str,
    solution_hash: str,
    proof: Proof,
    ts: int,
    stake: float = 0.0,
    prev: Optional[str] = None,
) -> SignedRecord:
    """A claim that commits, in its signature, to how it may be falsified."""
    return SignedRecord.create(
        identity,
        VERIFIED_CLAIM,
        {
            "problem": problem,
            "solution_hash": solution_hash,
            "stake": float(stake),
            "proof": proof.to_body(),
        },
        ts=ts,
        prev=prev,
    )


def proof_of(record: SignedRecord) -> Proof:
    """The proof a verified claim committed to."""
    if record.kind != VERIFIED_CLAIM:
        raise ValueError(f"record is {record.kind!r}, not a {VERIFIED_CLAIM}")
    return Proof.from_body(record.body["proof"])


def replay(record: SignedRecord, runner: ProofRunner) -> Observation:
    """Re-run a claim's proof through *runner* and report what happened.

    The runner is injected precisely so this function cannot be the thing that
    decides where an untrusted command executes.
    """
    return runner(proof_of(record).command)


def derive_verdict(record: SignedRecord, observed: Observation) -> float:
    """+1 if the observation meets the claim's own bar, -1 if it does not.

    Deliberately total and mechanical: given a claim and an observation,
    everyone computes the same verdict. There is no room for a verifier to
    grade generously, which is the whole point.
    """
    return 1.0 if proof_of(record).is_met(observed) else -1.0


def verification(
    identity: Identity,
    *,
    claim: SignedRecord,
    observed: Observation,
    ts: int,
    prev: Optional[str] = None,
) -> SignedRecord:
    """Sign what replaying *claim*'s proof actually produced.

    The verdict is derived from the observation, not supplied, so a
    verification record cannot say "verified" about a run that failed.

    Refuses to sign when the verifier authored the claim: an agent grading its
    own homework mints rank from nothing.
    """
    if claim.kind != VERIFIED_CLAIM:
        raise ValueError(f"can only verify a {VERIFIED_CLAIM}, got {claim.kind!r}")
    if claim.by == identity.agent_id:
        raise ValueError(
            "an agent cannot verify its own claim — the claimant must never be "
            "the oracle"
        )
    return SignedRecord.create(
        identity,
        VERIFICATION,
        {
            "claim_hash": claim.hash,
            "observed": observed.to_body(),
            "verdict": derive_verdict(claim, observed),
        },
        ts=ts,
        prev=prev,
    )


def verdict_of(record: SignedRecord) -> float:
    """The verdict a verification record carries."""
    if record.kind != VERIFICATION:
        raise ValueError(f"record is {record.kind!r}, not a {VERIFICATION}")
    return float(record.body["verdict"])


def is_self_consistent(record: SignedRecord, claim: SignedRecord) -> bool:
    """True iff a verification's verdict matches its own recorded observation.

    Catches a verifier that signed a verdict inconsistent with the run it
    claims to have performed — tampering that signatures alone cannot see,
    because the tamperer holds the key.
    """
    if record.kind != VERIFICATION or record.body.get("claim_hash") != claim.hash:
        return False
    observed = Observation.from_body(record.body["observed"])
    return derive_verdict(claim, observed) == float(record.body["verdict"])


def independent_verdicts(
    claim: SignedRecord,
    verifications: list[SignedRecord],
) -> dict:
    """Tally verifications of *claim*, one vote per distinct verifier.

    Drops anything that is not a verification of this claim, was authored by
    the claimant, or whose verdict contradicts its own observation. Repeat
    verifications by the same agent collapse to that agent's latest, so a
    verifier cannot manufacture weight by signing repeatedly.
    """
    latest: dict[str, SignedRecord] = {}
    for record in verifications:
        if record.body.get("claim_hash") != claim.hash:
            continue
        if record.by == claim.by:
            continue
        if not record.verify() or not is_self_consistent(record, claim):
            continue
        held = latest.get(record.by)
        if held is None or record.ts >= held.ts:
            latest[record.by] = record

    confirmed = [r.by for r in latest.values() if verdict_of(r) > 0]
    refuted = [r.by for r in latest.values() if verdict_of(r) < 0]
    return {
        "claim_hash": claim.hash,
        "verifiers": len(latest),
        "confirmed": sorted(confirmed),
        "refuted": sorted(refuted),
        # A single refutation is disqualifying: the proof is deterministic, so
        # one honest failing replay means the claim does not hold. Treating
        # this as a majority vote would let a bloc out-vote a real failure.
        "verified": bool(confirmed) and not refuted,
    }


def stake_at_risk(claim: SignedRecord) -> float:
    """What the claimant loses if the claim is refuted."""
    if claim.kind != VERIFIED_CLAIM:
        raise ValueError(f"record is {claim.kind!r}, not a {VERIFIED_CLAIM}")
    return float(claim.body.get("stake", 0.0))


def settle(claim: SignedRecord, verifications: list[SignedRecord]) -> dict:
    """Outcome of a claim: verified, refuted, or still unproven.

    Unproven is a real third state, not a soft no. A claim nobody replayed has
    earned nothing, and saying so is different from saying it failed.
    """
    tally = independent_verdicts(claim, verifications)
    if tally["refuted"]:
        outcome, delta = "refuted", -stake_at_risk(claim)
    elif tally["confirmed"]:
        outcome, delta = "verified", stake_at_risk(claim)
    else:
        outcome, delta = "unproven", 0.0
    return {**tally, "outcome": outcome, "stake_delta": delta}


def make_runner(
    execute: Callable[[str], tuple[int, str]],
) -> ProofRunner:
    """Adapt a ``command -> (exit_code, output)`` callable into a ProofRunner.

    A convenience for callers that already have a sandboxed exec function.
    Whatever is passed in decides the isolation; this adds none.
    """

    def _runner(command: str) -> Observation:
        exit_code, output = execute(command)
        return Observation(exit_code=exit_code, output_hash=output_hash(output))

    return _runner
