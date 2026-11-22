"""Exact first-passage comparison over every integer start offset.

The two benches keep their own local ticks. For offset ``d = right start - left
start`` local ticks ``tL`` and ``tR`` land on the same absolute tick exactly
when ``tL - tR == d``. Writing ``a_t`` / ``b_t`` for the two local first-hit
masses, the joint first-passage mass at offset ``d`` is the discrete
cross-correlation

    S_d = sum_t a_t * b_{t-d}.

The sequences may carry infinite geometric tails, so the candidate offsets and
the tail beyond the enumerated range are both certified with exact Fraction
arithmetic: no floating point and no truncated infinite sum.
"""
from fractions import Fraction

from analysis.first_pass import _effective_states, passage_solution
from analysis.process import PassageKernel
from review.sync import read_passage


def _full_product(side: PassageKernel, other: PassageKernel) -> tuple[PassageKernel, int]:
    """Product chain over the full Cartesian product of transient states."""
    side_size = len(side.direct_pass)
    other_size = len(other.direct_pass)
    index = {(i, j): i * other_size + j for i in range(side_size) for j in range(other_size)}
    continuation = []
    direct_pass = []
    for side_state in range(side_size):
        for other_state in range(other_size):
            direct_pass.append(
                side.direct_pass[side_state] * other.direct_pass[other_state])
            row = []
            for side_target, side_weight in side.continuation[side_state]:
                for other_target, other_weight in other.continuation[other_state]:
                    row.append((index[(side_target, other_target)], side_weight * other_weight))
            continuation.append(tuple(sorted(row)))
    initial = index[(side.initial, other.initial)]
    return PassageKernel(initial, tuple(continuation), tuple(direct_pass)), other_size


def _side_candidates(
    side: PassageKernel, other: PassageKernel,
) -> dict[int, Fraction]:
    """Scores S_d for d >= 0 with ``side`` the earlier-start local sequence.

    With the other bench starting d ticks later,

        S_d = sum_i (e_start Q_side^d)_i h_i,
        h_i = P(joint first passage | side state i, other start state),

    where h is read off the exact absorbing product-chain solution. The
    enumeration stops once a strict substochastic tail bound falls below the
    best score already found, so every omitted integer offset is certified
    suboptimal without enumerating the infinite tail.
    """
    product, other_size = _full_product(side, other)
    product_solution = passage_solution(product)
    h = [
        product_solution.get(side_state * other_size + other.initial, Fraction(0))
        for side_state in range(len(side.direct_pass))
    ]

    # Only side states that can still reach a pass edge contribute (every other
    # state has h_i = 0); mass that leaks into them is lost to the scores. The
    # effective sub-chain is strictly substochastic, so it always contracts even
    # when the original kernel contains a closed trap.
    effective = set(_effective_states(side))
    if side.initial not in effective:
        return {0: Fraction(0)}
    visits = passage_solution(side, [Fraction(1) if state in effective else Fraction(0)
                                     for state in range(len(side.direct_pass))])
    effective_visits = [visits[state] for state in effective]

    # u = (I - Q_eff)^-1 1 gives the expected visits before mass escapes; the
    # effective chain contracts by rho = 1 - 1/max(u) along its substochastic rows.
    maximum_visits = max(effective_visits)
    rho = 1 - 1 / maximum_visits if maximum_visits > 1 else Fraction(0)
    limit = max(h[state] for state in effective)
    start_visits = visits[side.initial]

    scores: dict[int, Fraction] = {}
    active = {side.initial: Fraction(1)}
    while True:
        value = sum((mass * h[state] for state, mass in active.items()), Fraction(0))
        offset = len(scores)
        scores[offset] = value
        next_active: dict[int, Fraction] = {}
        for state, mass in active.items():
            for target, weight in side.continuation[state]:
                if target in effective:
                    next_active[target] = next_active.get(target, Fraction(0)) + mass * weight
        if not next_active:
            break
        best = max(scores.values())
        tail_bound = limit * start_visits * rho ** (offset + 1) if rho else Fraction(0)
        if tail_bound < best:
            break
        active = next_active
    return scores


def stagger_scores(left_body: dict, right_body: dict) -> tuple[Fraction, dict[int, Fraction]]:
    """Return the joint eventual-pass mass and the finite map of offset scores."""
    left = read_passage(left_body)
    right = read_passage(right_body)
    left_pass = passage_solution(left)
    right_pass = passage_solution(right)
    joint = left_pass.get(left.initial, Fraction(0)) * right_pass.get(right.initial, Fraction(0))
    if joint == 0:
        return joint, {}

    # d >= 0: the right bench starts d ticks later, the left side leads.
    positive = _side_candidates(left, right)
    # d <= 0: mirror the benches and map gap e = -d onto the negative offsets.
    mirrored = _side_candidates(right, left)
    scores = dict(positive)
    for gap, value in mirrored.items():
        if gap:
            scores[-gap] = value
    return joint, scores


def best_offsets(scores: dict[int, Fraction]) -> tuple[int, ...]:
    if not scores:
        return ()
    top = max(scores.values())
    return tuple(sorted(offset for offset, value in scores.items() if value == top))
