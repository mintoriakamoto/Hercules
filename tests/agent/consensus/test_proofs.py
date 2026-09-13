"""Tests for replayable proofs — verification that cannot be talked into.

The property under test throughout is that a claim's standing comes from
re-running its proof, not from what any agent asserts about it.
"""

from __future__ import annotations

import pytest

from agent.consensus.identity import Identity
from agent.consensus.records import SignedRecord
from agent.consensus.proofs import (
    Observation,
    Proof,
    VERIFICATION,
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


@pytest.fixture
def miner():
    return Identity.generate()


@pytest.fixture
def checker():
    return Identity.generate()


def _claim(identity, *, proof=None, stake=0.0, ts=1000):
    return verified_claim(
        identity,
        problem="make the suite pass",
        solution_hash="abc123",
        proof=proof or Proof(command="pytest -q", expect_exit=0),
        ts=ts,
        stake=stake,
    )


class TestProofIsBoundToTheClaim:
    def test_claim_signature_covers_the_proof(self, miner):
        record = _claim(miner)
        assert record.verify() is True

        # Moving the bar after signing must invalidate the record: otherwise a
        # claimant could weaken its own test once the work is graded.
        tampered = SignedRecord(
            kind=record.kind,
            by=record.by,
            ts=record.ts,
            body={**record.body, "proof": Proof(command="true").to_body()},
            prev=record.prev,
            sig=record.sig,
        )
        assert tampered.verify() is False

    def test_proof_round_trips(self, miner):
        proof = Proof(command="pytest -q", expect_exit=0, expect_output_hash="deadbeef")
        assert proof_of(_claim(miner, proof=proof)) == proof

    def test_proof_of_rejects_a_non_claim(self, miner):
        record = SignedRecord.create(miner, "something_else", {}, ts=1)
        with pytest.raises(ValueError, match="not a verified_claim"):
            proof_of(record)


class TestVerdictIsDerivedNotAsserted:
    def test_meeting_the_bar_verifies(self, miner):
        record = _claim(miner)
        assert derive_verdict(record, Observation(exit_code=0)) == 1.0

    def test_missing_the_bar_refutes(self, miner):
        record = _claim(miner)
        assert derive_verdict(record, Observation(exit_code=1)) == -1.0

    def test_output_hash_is_enforced_when_pinned(self, miner):
        record = _claim(
            miner, proof=Proof(command="bench", expect_exit=0, expect_output_hash="aaa")
        )
        assert derive_verdict(record, Observation(0, output_hash="aaa")) == 1.0
        assert derive_verdict(record, Observation(0, output_hash="bbb")) == -1.0

    def test_output_is_ignored_when_not_pinned(self, miner):
        record = _claim(miner)
        assert derive_verdict(record, Observation(0, output_hash="anything")) == 1.0

    def test_a_verifier_cannot_sign_a_verdict_it_did_not_observe(self, miner, checker):
        """The verdict is computed from the observation, never supplied."""
        record = _claim(miner)
        signed = verification(
            checker, claim=record, observed=Observation(exit_code=1), ts=2000
        )
        assert verdict_of(signed) == -1.0, "a failing run cannot be signed as verified"


class TestClaimantIsNeverTheOracle:
    def test_self_verification_is_refused(self, miner):
        record = _claim(miner)
        with pytest.raises(ValueError, match="cannot verify its own claim"):
            verification(miner, claim=record, observed=Observation(0), ts=2000)

    def test_self_verification_is_dropped_from_a_tally(self, miner, checker):
        """Even if one is forged by hand, it must not count."""
        record = _claim(miner)
        forged = SignedRecord.create(
            miner,
            VERIFICATION,
            {
                "claim_hash": record.hash,
                "observed": Observation(0).to_body(),
                "verdict": 1.0,
            },
            ts=2000,
        )
        assert forged.verify() is True, "it is a validly signed record"
        tally = independent_verdicts(record, [forged])
        assert tally["verifiers"] == 0
        assert tally["verified"] is False

    def test_an_independent_verifier_counts(self, miner, checker):
        record = _claim(miner)
        signed = verification(checker, claim=record, observed=Observation(0), ts=2000)
        tally = independent_verdicts(record, [signed])
        assert tally["verified"] is True
        assert tally["confirmed"] == [checker.agent_id]


class TestForgedVerdicts:
    def test_verdict_contradicting_its_own_observation_is_rejected(self, miner, checker):
        record = _claim(miner)
        lying = SignedRecord.create(
            checker,
            VERIFICATION,
            {
                "claim_hash": record.hash,
                "observed": Observation(exit_code=1).to_body(),  # it failed
                "verdict": 1.0,  # but claims success

            },
            ts=2000,
        )
        assert is_self_consistent(lying, record) is False
        assert independent_verdicts(record, [lying])["verifiers"] == 0

    def test_honest_verification_is_self_consistent(self, miner, checker):
        record = _claim(miner)
        signed = verification(checker, claim=record, observed=Observation(1), ts=2000)
        assert is_self_consistent(signed, record) is True


class TestTally:
    def test_one_refutation_disqualifies_against_many_confirmations(self, miner):
        """The proof is deterministic: one honest failing replay settles it."""
        record = _claim(miner)
        records = [
            verification(Identity.generate(), claim=record, observed=Observation(0), ts=2000)
            for _ in range(5)
        ]
        records.append(
            verification(
                Identity.generate(), claim=record, observed=Observation(1), ts=2000
            )
        )
        tally = independent_verdicts(record, records)
        assert len(tally["confirmed"]) == 5
        assert len(tally["refuted"]) == 1
        assert tally["verified"] is False, "a bloc must not out-vote a real failure"

    def test_a_verifier_cannot_manufacture_weight_by_repeating(self, miner, checker):
        record = _claim(miner)
        records = [
            verification(checker, claim=record, observed=Observation(0), ts=2000 + n)
            for n in range(10)
        ]
        assert independent_verdicts(record, records)["verifiers"] == 1

    def test_a_verifier_changing_its_mind_uses_its_latest(self, miner, checker):
        record = _claim(miner)
        first = verification(checker, claim=record, observed=Observation(0), ts=2000)
        later = verification(checker, claim=record, observed=Observation(1), ts=3000)
        tally = independent_verdicts(record, [first, later])
        assert tally["refuted"] == [checker.agent_id]
        assert tally["verified"] is False

    def test_verifications_of_other_claims_are_ignored(self, miner, checker):
        record = _claim(miner)
        other = _claim(miner, ts=9999)
        stray = verification(checker, claim=other, observed=Observation(0), ts=2000)
        assert independent_verdicts(record, [stray])["verifiers"] == 0


class TestSettlement:
    def test_unproven_is_distinct_from_refuted(self, miner):
        record = _claim(miner, stake=5.0)
        result = settle(record, [])
        assert result["outcome"] == "unproven"
        assert result["stake_delta"] == 0.0, "nobody checked; nothing is lost"

    def test_verified_claim_earns_its_stake(self, miner, checker):
        record = _claim(miner, stake=5.0)
        signed = verification(checker, claim=record, observed=Observation(0), ts=2000)
        result = settle(record, [signed])
        assert result["outcome"] == "verified"
        assert result["stake_delta"] == 5.0

    def test_refuted_claim_loses_its_stake(self, miner, checker):
        record = _claim(miner, stake=5.0)
        signed = verification(checker, claim=record, observed=Observation(1), ts=2000)
        result = settle(record, [signed])
        assert result["outcome"] == "refuted"
        assert result["stake_delta"] == -5.0

    def test_stake_defaults_to_zero(self, miner):
        assert stake_at_risk(_claim(miner)) == 0.0


class TestReplayNeverExecutes:
    def test_replay_delegates_to_the_injected_runner(self, miner):
        record = _claim(miner, proof=Proof(command="pytest -q"))
        seen = []

        def runner(command):
            seen.append(command)
            return Observation(exit_code=0)

        assert replay(record, runner) == Observation(exit_code=0)
        assert seen == ["pytest -q"], "the command must reach the caller's sandbox"

    def test_make_runner_adapts_an_exec_callable(self, miner):
        record = _claim(miner)
        runner = make_runner(lambda command: (0, "all good"))
        observed = replay(record, runner)
        assert observed.exit_code == 0
        assert observed.output_hash == output_hash("all good")

    def test_output_hash_is_stable_across_str_and_bytes(self):
        assert output_hash("same") == output_hash(b"same")
