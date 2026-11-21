from dataclasses import dataclass
from fractions import Fraction

from protocol.model import Revision


@dataclass(frozen=True, slots=True)
class PassageKernel:
    initial: int
    continuation: tuple[tuple[tuple[int, Fraction], ...], ...]
    direct_pass: tuple[Fraction, ...]


@dataclass(frozen=True, slots=True)
class TransientProcess:
    states: tuple[str, ...]
    kernel: PassageKernel
    direct_fail: tuple[Fraction, ...]


def build_process(revision: Revision) -> TransientProcess:
    protocol = revision.protocol
    terminals = {protocol.pass_state, protocol.fail_state}
    states = tuple(state for state in protocol.states if state not in terminals)
    indices = {name: index for index, name in enumerate(states)}
    continuing = [{} for _ in states]
    direct_pass = [Fraction(0) for _ in states]
    direct_fail = [Fraction(0) for _ in states]

    for edge in protocol.transitions:
        if not edge.probability:
            continue
        source = indices[edge.source]
        if edge.destination == protocol.pass_state:
            direct_pass[source] += edge.probability
        elif edge.destination == protocol.fail_state:
            direct_fail[source] += edge.probability
        else:
            destination = indices[edge.destination]
            row = continuing[source]
            row[destination] = row.get(destination, Fraction(0)) + edge.probability

    kernel = PassageKernel(
        indices[protocol.start],
        tuple(tuple(sorted(row.items())) for row in continuing),
        tuple(direct_pass),
    )
    return TransientProcess(states, kernel, tuple(direct_fail))
