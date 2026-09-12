"""Durability tests — a chain read back from disk must be as good as one in memory."""

from __future__ import annotations

import os
import stat

import pytest

from agent.consensus.identity import Identity
from agent.consensus.proofs import Observation, Proof, verification, verified_claim
from agent.consensus.records import SignedRecord
from agent.consensus.store import (
    PersistentEvidenceLog,
    consensus_home,
    load_or_create_identity,
)


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERCULES_CONSENSUS_HOME", str(tmp_path / "consensus"))
    # The SQLite path is cached per-process; clear it between tests.
    import agent.consensus.store as store

    store._initialized.clear()


def _claim(identity, ts=1000):
    return verified_claim(
        identity,
        problem="p",
        solution_hash="s",
        proof=Proof(command="pytest -q"),
        ts=ts,
        stake=1.0,
    )


class TestIdentityPersistence:
    def test_identity_is_stable_across_calls(self):
        first = load_or_create_identity()
        second = load_or_create_identity()
        assert first.agent_id == second.agent_id, "rank must survive a restart"

    def test_seed_is_not_world_readable(self):
        load_or_create_identity()
        seed_path = consensus_home() / "identity.seed"
        mode = stat.S_IMODE(os.stat(seed_path).st_mode)
        assert mode == 0o600, f"seed is the private key; mode was {oct(mode)}"

    def test_a_corrupt_seed_is_refused_not_guessed(self):
        home = consensus_home()
        home.mkdir(parents=True, exist_ok=True)
        (home / "identity.seed").write_bytes(b"too short")
        with pytest.raises(ValueError, match="32-byte"):
            load_or_create_identity()


class TestChainSurvivesTheRoundTrip:
    def test_records_come_back_in_order_and_verify(self):
        identity = Identity.generate()
        log = PersistentEvidenceLog()
        first = _claim(identity, ts=1)
        log.append(first)
        second = _claim(identity, ts=2)
        second = SignedRecord.create(
            identity, second.kind, second.body, ts=2, prev=first.hash
        )
        log.append(second)

        reopened = PersistentEvidenceLog()
        assert len(reopened) == 2
        assert [r.hash for r in reopened.records()] == [first.hash, second.hash]
        assert reopened.verify_chain() is True

    def test_head_advances_and_persists(self):
        identity = Identity.generate()
        log = PersistentEvidenceLog()
        assert log.head is None
        record = _claim(identity)
        log.append(record)
        assert PersistentEvidenceLog().head == record.hash

    def test_append_refuses_a_broken_prev_link(self):
        identity = Identity.generate()
        log = PersistentEvidenceLog()
        log.append(_claim(identity, ts=1))
        # prev=None again: this would fork the chain.
        with pytest.raises(ValueError, match="prev-hash mismatch"):
            log.append(_claim(identity, ts=2))

    def test_append_refuses_an_unsigned_record(self):
        identity = Identity.generate()
        forged = SignedRecord(
            kind="verified_claim", by=identity.agent_id, ts=1, body={}, prev=None, sig=""
        )
        with pytest.raises(ValueError, match="signature is invalid"):
            PersistentEvidenceLog().append(forged)

    def test_tampering_with_a_stored_record_breaks_the_chain(self):
        identity = Identity.generate()
        log = PersistentEvidenceLog()
        log.append(_claim(identity))

        import json
        import sqlite3

        from agent.consensus.store import _db_path

        conn = sqlite3.connect(_db_path())
        row = conn.execute("SELECT seq, record FROM evidence").fetchone()
        payload = json.loads(row[1])
        payload["body"]["problem"] = "a different problem entirely"
        conn.execute(
            "UPDATE evidence SET record = ? WHERE seq = ?",
            (json.dumps(payload), row[0]),
        )
        conn.commit()
        conn.close()

        assert PersistentEvidenceLog().verify_chain() is False

    def test_records_of_kind_filters(self):
        miner, checker = Identity.generate(), Identity.generate()
        log = PersistentEvidenceLog()
        claim_record = _claim(miner)
        log.append(claim_record)
        check = verification(
            checker, claim=claim_record, observed=Observation(0), ts=2, prev=claim_record.hash
        )
        log.append(check)
        assert len(log.records_of_kind("verified_claim")) == 1
        assert len(log.records_of_kind("verification")) == 1
