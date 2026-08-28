"""Tests for the web-of-trust consensus primitives (agent.consensus)."""

from __future__ import annotations

import pytest

from agent.consensus import (
    EvidenceLog,
    Identity,
    SignedRecord,
    TrustGraph,
    canonical_bytes,
    claim,
    content_hash,
    graph_from_validations,
    validation,
    verify,
)


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_generate_is_unique(self):
        assert Identity.generate().agent_id != Identity.generate().agent_id

    def test_seed_roundtrip_preserves_identity(self):
        original = Identity.generate()
        restored = Identity.from_seed(original.seed())
        assert restored.agent_id == original.agent_id
        # And the restored key produces signatures the original id verifies.
        sig = restored.sign(b"hello")
        assert verify(original.agent_id, b"hello", sig)

    def test_from_seed_rejects_wrong_length(self):
        with pytest.raises(ValueError):
            Identity.from_seed(b"too-short")

    def test_sign_and_verify(self):
        ident = Identity.generate()
        sig = ident.sign(b"payload")
        assert verify(ident.agent_id, b"payload", sig) is True

    def test_verify_rejects_tampered_message(self):
        ident = Identity.generate()
        sig = ident.sign(b"payload")
        assert verify(ident.agent_id, b"payload-tampered", sig) is False

    def test_verify_rejects_wrong_key(self):
        a, b = Identity.generate(), Identity.generate()
        sig = a.sign(b"payload")
        assert verify(b.agent_id, b"payload", sig) is False

    def test_verify_never_raises_on_garbage(self):
        assert verify("not-a-key", b"x", "not-a-sig") is False
        assert verify("", b"", "") is False


# ---------------------------------------------------------------------------
# records + evidence log
# ---------------------------------------------------------------------------


class TestRecords:
    def test_canonical_is_deterministic_regardless_of_key_order(self):
        assert canonical_bytes({"b": 1, "a": 2}) == canonical_bytes({"a": 2, "b": 1})

    def test_content_hash_stable(self):
        assert content_hash({"x": 1}) == content_hash({"x": 1})
        assert content_hash({"x": 1}) != content_hash({"x": 2})

    def test_signed_record_verifies(self):
        ident = Identity.generate()
        rec = SignedRecord.create(ident, "claim", {"n": 1}, ts=100)
        assert rec.by == ident.agent_id
        assert rec.verify() is True

    def test_tampering_body_breaks_signature(self):
        ident = Identity.generate()
        rec = SignedRecord.create(ident, "claim", {"n": 1}, ts=100)
        forged = SignedRecord(
            kind=rec.kind, by=rec.by, ts=rec.ts, body={"n": 999},
            prev=rec.prev, sig=rec.sig,
        )
        assert forged.verify() is False

    def test_unsigned_record_does_not_verify(self):
        rec = SignedRecord(kind="claim", by="whoever", ts=1, body={})
        assert rec.verify() is False

    def test_to_from_dict_roundtrip(self):
        ident = Identity.generate()
        rec = claim(ident, problem="p", solution_hash="abc", ts=5, stake=2.0)
        again = SignedRecord.from_dict(rec.to_dict())
        assert again.hash == rec.hash
        assert again.verify() is True

    def test_validation_clamps_verdict(self):
        ident = Identity.generate()
        assert validation(ident, claim_hash="h", verdict=5.0, ts=1).body["verdict"] == 1.0
        assert validation(ident, claim_hash="h", verdict=-9.0, ts=1).body["verdict"] == -1.0


class TestEvidenceLog:
    def test_append_and_chain(self):
        ident = Identity.generate()
        log = EvidenceLog()
        assert log.head is None

        r1 = SignedRecord.create(ident, "claim", {"n": 1}, ts=1, prev=None)
        log.append(r1)
        assert log.head == r1.hash

        r2 = SignedRecord.create(ident, "claim", {"n": 2}, ts=2, prev=log.head)
        log.append(r2)
        assert len(log) == 2
        assert log.verify_chain() is True

    def test_rejects_bad_prev_link(self):
        ident = Identity.generate()
        log = EvidenceLog()
        log.append(SignedRecord.create(ident, "claim", {"n": 1}, ts=1, prev=None))
        # A record pointing at the wrong prev (None instead of head) is refused.
        orphan = SignedRecord.create(ident, "claim", {"n": 2}, ts=2, prev=None)
        with pytest.raises(ValueError, match="prev-hash mismatch"):
            log.append(orphan)

    def test_rejects_bad_signature(self):
        ident = Identity.generate()
        log = EvidenceLog()
        bad = SignedRecord(kind="claim", by=ident.agent_id, ts=1, body={}, sig="AAAA")
        with pytest.raises(ValueError, match="signature is invalid"):
            log.append(bad)

    def test_verify_chain_detects_reorder(self):
        ident = Identity.generate()
        r1 = SignedRecord.create(ident, "claim", {"n": 1}, ts=1, prev=None)
        r2 = SignedRecord.create(ident, "claim", {"n": 2}, ts=2, prev=r1.hash)
        log = EvidenceLog()
        log.append(r1)
        log.append(r2)
        # Swap order behind the log's back — the chain must now fail to verify.
        log._records = [r2, r1]  # noqa: SLF001 - deliberate tamper
        assert log.verify_chain() is False


# ---------------------------------------------------------------------------
# web of trust
# ---------------------------------------------------------------------------


class TestTrustGraph:
    def test_root_trusts_itself_fully(self):
        g = TrustGraph()
        assert g.reputation("root", "root") == 1.0

    def test_direct_edge(self):
        g = TrustGraph()
        g.add_opinion("root", "alice", 1.0)
        # one hop: 1.0 * 1.0 * decay(0.5)
        assert g.reputation("root", "alice", decay=0.5) == pytest.approx(0.5)

    def test_two_hops_decay(self):
        g = TrustGraph()
        g.add_opinion("root", "alice", 1.0)
        g.add_opinion("alice", "bob", 1.0)
        # 1.0 * 1.0 * 0.5 (to alice) * 1.0 * 0.5 (to bob) = 0.25
        assert g.reputation("root", "bob", decay=0.5) == pytest.approx(0.25)

    def test_self_edges_ignored(self):
        g = TrustGraph()
        g.add_opinion("alice", "alice", 1.0)
        assert g.edge_weight("alice", "alice") is None

    def test_opinions_are_averaged(self):
        g = TrustGraph()
        g.add_opinion("root", "alice", 1.0)
        g.add_opinion("root", "alice", 0.0)
        assert g.edge_weight("root", "alice") == pytest.approx(0.5)

    def test_sybil_cluster_scores_zero(self):
        """A pack of fake agents who only vouch for each other is invisible."""
        g = TrustGraph()
        # root trusts alice
        g.add_opinion("root", "alice", 1.0)
        # a sybil ring: sybil0..sybil4 all vouch for sybil0, but no one the root
        # trusts vouches for any of them.
        for i in range(5):
            g.add_opinion(f"sybil{i}", "sybil0", 1.0)
        assert g.reputation("root", "sybil0") == 0.0
        assert g.reputation("root", "alice") > 0.0

    def test_sybil_gains_only_via_a_trusted_voucher(self):
        g = TrustGraph()
        g.add_opinion("root", "alice", 1.0)
        for i in range(5):
            g.add_opinion(f"sybil{i}", "sybil0", 1.0)
        # Alice (trusted) vouches for sybil0 — now and only now it earns some.
        g.add_opinion("alice", "sybil0", 1.0)
        assert g.reputation("root", "sybil0") > 0.0

    def test_distrust_is_direct_but_not_transitive(self):
        g = TrustGraph()
        g.add_opinion("root", "mallory", -1.0)   # root directly distrusts mallory
        g.add_opinion("mallory", "victim", 1.0)  # mallory vouches for victim
        # mallory scores negative from root...
        assert g.reputation("root", "mallory") < 0.0
        # ...and cannot launder trust onward: victim gets nothing via mallory.
        assert g.reputation("root", "victim") == 0.0

    def test_depth_limit_cuts_off_far_agents(self):
        g = TrustGraph()
        chain = ["root", "a", "b", "c", "d"]
        for src, dst in zip(chain, chain[1:]):
            g.add_opinion(src, dst, 1.0)
        assert g.reputation("root", "d", max_depth=4) > 0.0
        assert g.reputation("root", "d", max_depth=2) == 0.0

    def test_ranking_orders_by_reputation(self):
        g = TrustGraph()
        g.add_opinion("root", "alice", 1.0)
        g.add_opinion("alice", "bob", 1.0)
        ranked = g.ranking("root")
        agents = [a for a, _ in ranked]
        assert agents[0] == "alice"  # closer to root ⇒ higher
        assert "bob" in agents
        assert "root" not in agents


class TestGraphFromValidations:
    def test_builds_edges_from_signed_validations(self):
        root, alice = Identity.generate(), Identity.generate()
        c = claim(alice, problem="p", solution_hash="s", ts=1)
        v = validation(root, claim_hash=c.hash, verdict=1.0, ts=2)

        g = graph_from_validations([v], claims_by_hash={c.hash: c.by})
        assert g.edge_weight(root.agent_id, alice.agent_id) == pytest.approx(1.0)

    def test_forged_validation_is_ignored(self):
        root, alice = Identity.generate(), Identity.generate()
        c = claim(alice, problem="p", solution_hash="s", ts=1)
        v = validation(root, claim_hash=c.hash, verdict=1.0, ts=2)
        # Corrupt the signature — the edge must not be created.
        forged = SignedRecord(
            kind=v.kind, by=v.by, ts=v.ts, body=v.body, prev=v.prev, sig="AAAA"
        )
        g = graph_from_validations([forged], claims_by_hash={c.hash: c.by})
        assert g.edge_weight(root.agent_id, alice.agent_id) is None

    def test_end_to_end_reputation(self):
        """Signed claims + signed validations ⇒ a usable reputation ranking."""
        root = Identity.generate()
        alice = Identity.generate()
        bob = Identity.generate()

        # Alice and Bob each claim a solution.
        ca = claim(alice, problem="p1", solution_hash="a", ts=1)
        cb = claim(bob, problem="p2", solution_hash="b", ts=1)
        claims_by_hash = {ca.hash: ca.by, cb.hash: cb.by}

        # Root validates Alice's solution; Alice validates Bob's.
        validations = [
            validation(root, claim_hash=ca.hash, verdict=1.0, ts=2),
            validation(alice, claim_hash=cb.hash, verdict=1.0, ts=3),
        ]

        g = graph_from_validations(validations, claims_by_hash=claims_by_hash)
        rep_alice = g.reputation(root.agent_id, alice.agent_id)
        rep_bob = g.reputation(root.agent_id, bob.agent_id)
        assert rep_alice > rep_bob > 0.0  # alice is closer to the root than bob
