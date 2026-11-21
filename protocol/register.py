from collections.abc import Iterable

from protocol.model import Protocol, Transition
from protocol.revision import RevisionStore
from protocol.validate import InvalidProtocol


def revise(
    store: RevisionStore,
    bench_id: str,
    *,
    states: Iterable[str],
    start: str,
    pass_state: str,
    fail_state: str,
    transitions: Iterable[Transition],
) -> str:
    if isinstance(states, (str, bytes)):
        raise InvalidProtocol('states must be an iterable of state names')
    try:
        state_snapshot = tuple(states)
        edge_snapshot = tuple(transitions)
    except TypeError as exc:
        raise InvalidProtocol('states and transitions must be iterable') from exc
    protocol = Protocol(bench_id, state_snapshot, start, pass_state, fail_state, edge_snapshot)
    return store.append(protocol)
