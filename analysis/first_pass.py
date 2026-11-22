from collections.abc import Sequence
from collections import deque
from fractions import Fraction

from analysis.linear import solve_exact
from analysis.process import PassageKernel


def first_hit_mass(kernel: PassageKernel, tick: int) -> Fraction:
    if type(tick) is not int or tick < 1:
        raise ValueError('tick must be a positive integer')
    active = {kernel.initial: Fraction(1)}
    for _ in range(1, tick):
        next_active: dict[int, Fraction] = {}
        for state, mass in active.items():
            for target, weight in kernel.continuation[state]:
                next_active[target] = next_active.get(target, Fraction(0)) + mass * weight
        if not next_active:
            return Fraction(0)
        active = next_active
    return sum((mass * kernel.direct_pass[state] for state, mass in active.items()), Fraction(0))


def _effective_states(kernel: PassageKernel) -> list[int]:
    predecessors: list[list[int]] = [[] for _ in kernel.direct_pass]
    for source, row in enumerate(kernel.continuation):
        for target, weight in row:
            if weight > 0:
                predecessors[target].append(source)
    effective = {state for state, weight in enumerate(kernel.direct_pass) if weight > 0}
    pending = deque(sorted(effective))
    while pending:
        for source in predecessors[pending.popleft()]:
            if source not in effective:
                effective.add(source)
                pending.append(source)
    return sorted(effective)


def passage_solution(kernel: PassageKernel, rhs: Sequence[Fraction] | None = None) -> dict[int, Fraction]:
    """Solve (I - Q_eff) x = r over the states that can still reach a pass edge.

    Returns the solution keyed by the kernel's state indices. States outside
    the effective domain (traps and failure paths) are treated as zero. With
    the default direct-pass right-hand side the value at ``kernel.initial`` is
    exactly the eventual passage mass.
    """
    effective = _effective_states(kernel)
    positions = {state: position for position, state in enumerate(effective)}
    if rhs is None:
        right = [kernel.direct_pass[state] for state in effective]
    else:
        right = [Fraction(rhs[state]) for state in effective]
    size = len(effective)
    matrix = []
    for position, state in enumerate(effective):
        row = [Fraction(0)] * size
        row[position] = Fraction(1)
        for target, weight in kernel.continuation[state]:
            if target in positions:
                row[positions[target]] -= weight
        matrix.append(row)
    # Flows leaving the effective domain retain their mass and contribute zero to passage.
    solved = solve_exact(matrix, right)
    return {state: solved[positions[state]] for state in effective}


def eventual_pass_mass(kernel: PassageKernel) -> Fraction:
    solution = passage_solution(kernel)
    return solution.get(kernel.initial, Fraction(0))
