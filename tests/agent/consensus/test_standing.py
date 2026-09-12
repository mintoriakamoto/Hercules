"""Standing tests — the reward must not corrupt the thing that grants it."""

from __future__ import annotations

from agent.consensus.identity import Identity
from agent.consensus.proofs import (
    Observation,
    Proof,
    independent_verdicts,
    verification,
    verified_claim,
)
from agent.consensus.standing import (
    DEFAULT_HALF_LIFE_SECONDS,
    compute_allocation,
    may_validate,
    ranked,
    standings,
)

NOW = 1_000_000


def _claim(identity, *, ts=NOW, stake=0.0, problem="p"):
    return verified_claim(
        identity,
        problem=problem,
        solution_hash="s",
        proof=Proof(command="pytest -q"),
        ts=ts,
        stake=stake,
    )


def _pass(checker, claim, ts=NOW):
    return verification(checker, claim=claim, observed=Observation(0), ts=ts)


def _fail(checker, claim, ts=NOW):
    return verification(checker, claim=claim, observed=Observation(1), ts=ts)


class TestRankBuysResourcesNeverTruth:
    def test_a_high_ranked_agent_cannot_overturn_a_refutation(self):
        """The invariant the whole scheme rests on."""
        miner = Identity.generate()
        titan = Identity.generate()
        nobody = Identity.generate()

        # Give `titan` a large standing from a long history of verified work.
        history = [_claim(titan, problem=f"p{n}", stake=10.0) for n in range(20)]
        checks = [_pass(Identity.generate(), c) for c in history]
        board = standings(history, checks, now=NOW)
        assert board[titan.agent_id].rank > 100

        # Now titan confirms a claim that `nobody` refutes.
        disputed = _claim(miner)
        verdicts = [_pass(titan, disputed), _fail(nobody, disputed)]
        tally = independent_verdicts(disputed, verdicts)

        assert tally["verified"] is False, (
            "standing must not buy influence over what counts as verified"
        )

    def test_may_validate_ignores_standing_entirely(self):
        miner, other = Identity.generate(), Identity.generate()
        claim = _claim(miner)
        assert may_validate(claim, other.agent_id) is True
        assert may_validate(claim, miner.agent_id) is False


class TestRankFromSettledClaims:
    def test_verified_work_earns_rank(self):
        miner, checker = Identity.generate(), Identity.generate()
        claim = _claim(miner)
        board = standings([claim], [_pass(checker, claim)], now=NOW)
        assert board[miner.agent_id].rank > 0
        assert board[miner.agent_id].verified == 1

    def test_refuted_work_costs_rank(self):
        miner, checker = Identity.generate(), Identity.generate()
        claim = _claim(miner)
        board = standings([claim], [_fail(checker, claim)], now=NOW)
        assert board[miner.agent_id].rank < 0
        assert board[miner.agent_id].refuted == 1

    def test_unproven_work_moves_nothing(self):
        miner = Identity.generate()
        claim = _claim(miner, stake=5.0)
        board = standings([claim], [], now=NOW)
        assert board[miner.agent_id].rank == 0.0
        assert board[miner.agent_id].verified == 0
        assert board[miner.agent_id].refuted == 0

    def test_stake_amplifies_the_reward(self):
        cautious, bold, checker = (
            Identity.generate(),
            Identity.generate(),
            Identity.generate(),
        )
        low, high = _claim(cautious, stake=0.0), _claim(bold, stake=9.0)
        board = standings([low, high], [_pass(checker, low), _pass(checker, high)], now=NOW)
        assert board[bold.agent_id].rank > board[cautious.agent_id].rank

    def test_stake_amplifies_the_penalty_too(self):
        cautious, bold, checker = (
            Identity.generate(),
            Identity.generate(),
            Identity.generate(),
        )
        low, high = _claim(cautious, stake=0.0), _claim(bold, stake=9.0)
        board = standings([low, high], [_fail(checker, low), _fail(checker, high)], now=NOW)
        assert board[bold.agent_id].rank < board[cautious.agent_id].rank


class TestPositionDecays:
    def test_standing_falls_without_new_work(self):
        miner, checker = Identity.generate(), Identity.generate()
        old = _claim(miner, ts=NOW - DEFAULT_HALF_LIFE_SECONDS)
        fresh_board = standings([old], [_pass(checker, old)], now=old.ts)
        aged_board = standings([old], [_pass(checker, old)], now=NOW)
        assert aged_board[miner.agent_id].rank < fresh_board[miner.agent_id].rank

    def test_one_half_life_halves_the_contribution(self):
        miner, checker = Identity.generate(), Identity.generate()
        claim = _claim(miner, ts=NOW - DEFAULT_HALF_LIFE_SECONDS)
        board = standings([claim], [_pass(checker, claim)], now=NOW)
        assert board[miner.agent_id].rank == 0.5

    def test_a_seat_must_be_re_earned(self):
        veteran, newcomer, checker = (
            Identity.generate(),
            Identity.generate(),
            Identity.generate(),
        )
        # Veteran's win is four half-lives old; newcomer's is today.
        stale = _claim(veteran, ts=NOW - 4 * DEFAULT_HALF_LIFE_SECONDS, stake=3.0)
        recent = _claim(newcomer, ts=NOW)
        board = standings(
            [stale, recent], [_pass(checker, stale), _pass(checker, recent)], now=NOW
        )
        assert board[newcomer.agent_id].rank > board[veteran.agent_id].rank


class TestConcentrationIsDampened:
    def test_a_dominant_agent_cannot_take_everything(self):
        """Unbounded positive feedback ends in a monoculture."""
        whale, minnow, checker = (
            Identity.generate(),
            Identity.generate(),
            Identity.generate(),
        )
        big = [_claim(whale, problem=f"p{n}", stake=50.0) for n in range(30)]
        small = [_claim(minnow, problem="tiny")]
        checks = [_pass(checker, c) for c in big + small]
        board = standings(big + small, checks, now=NOW)

        assert board[whale.agent_id].rank > 100 * board[minnow.agent_id].rank
        assert board[minnow.agent_id].compute_share >= 0.09, (
            "the reserved slice must survive an overwhelming rank gap"
        )

    def test_shares_sum_to_one(self):
        a, b, c, checker = (Identity.generate() for _ in range(4))
        claims = [_claim(a), _claim(b, stake=2.0), _claim(c, stake=5.0)]
        checks = [_pass(checker, x) for x in claims]
        board = standings(claims, checks, now=NOW)
        assert abs(sum(s.compute_share for s in board.values()) - 1.0) < 1e-6

    def test_a_refuted_agent_still_gets_its_reserved_slice(self):
        """An agent that can never work can never show it improved."""
        failure, winner, checker = (
            Identity.generate(),
            Identity.generate(),
            Identity.generate(),
        )
        bad, good = _claim(failure), _claim(winner)
        board = standings(
            [bad, good], [_fail(checker, bad), _pass(checker, good)], now=NOW
        )
        assert board[failure.agent_id].rank < 0
        assert board[failure.agent_id].compute_share > 0

    def test_reserved_fraction_of_zero_is_winner_take_all(self):
        whale, minnow, checker = (
            Identity.generate(),
            Identity.generate(),
            Identity.generate(),
        )
        big = _claim(whale, stake=100.0)
        small = _claim(minnow)
        board = standings(
            [big, small],
            [_pass(checker, big), _pass(checker, small)],
            now=NOW,
            reserved_fraction=0.0,
        )
        assert board[minnow.agent_id].compute_share < 0.02


class TestAllocation:
    def test_compute_is_split_by_share(self):
        a, b, checker = Identity.generate(), Identity.generate(), Identity.generate()
        claims = [_claim(a, stake=9.0), _claim(b)]
        board = standings(claims, [_pass(checker, c) for c in claims], now=NOW)
        allocation = compute_allocation(board, 100.0)
        assert abs(sum(allocation.values()) - 100.0) < 1e-3
        assert allocation[a.agent_id] > allocation[b.agent_id]

    def test_ranked_orders_best_first(self):
        a, b, checker = Identity.generate(), Identity.generate(), Identity.generate()
        claims = [_claim(a), _claim(b, stake=9.0)]
        board = standings(claims, [_pass(checker, c) for c in claims], now=NOW)
        assert ranked(board)[0].agent_id == b.agent_id

    def test_no_claims_means_no_standings(self):
        assert standings([], [], now=NOW) == {}
