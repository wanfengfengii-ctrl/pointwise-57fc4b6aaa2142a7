from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class Transition:
    source: str
    destination: str
    probability: Fraction


@dataclass(frozen=True, slots=True)
class Protocol:
    bench_id: str
    states: tuple[str, ...]
    start: str
    pass_state: str
    fail_state: str
    transitions: tuple[Transition, ...]


@dataclass(frozen=True, slots=True)
class Revision:
    revision_id: str
    protocol: Protocol
