from fractions import Fraction

from protocol.model import Protocol, Transition


class InvalidProtocol(ValueError):
    pass


def _is_name(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        value.encode('utf-8')
    except UnicodeEncodeError:
        return False
    return True


def validate_protocol(protocol: Protocol) -> None:
    if not _is_name(protocol.bench_id):
        raise InvalidProtocol('a bench must have a valid name')
    if not isinstance(protocol.states, tuple) or not all(map(_is_name, protocol.states)):
        raise InvalidProtocol('states must be a tuple of valid names')
    states = set(protocol.states)
    if len(states) != len(protocol.states):
        raise InvalidProtocol('state names must be unique')
    for role, name in (
        ('initial', protocol.start), ('pass', protocol.pass_state), ('fail', protocol.fail_state),
    ):
        if not _is_name(name) or name not in states:
            raise InvalidProtocol(f'{role} state must be declared')
    terminals = {protocol.pass_state, protocol.fail_state}
    if len(terminals) != 2 or protocol.start in terminals:
        raise InvalidProtocol('the two terminals and the initial state must be distinct')
    if not isinstance(protocol.transitions, tuple):
        raise InvalidProtocol('transitions must be a tuple')

    totals = {state: Fraction(0) for state in protocol.states if state not in terminals}
    for edge in protocol.transitions:
        if not isinstance(edge, Transition):
            raise InvalidProtocol('each edge must be a Transition')
        if not _is_name(edge.source) or edge.source not in totals:
            raise InvalidProtocol(f'edge from undeclared or terminal state {edge.source!r}')
        if not _is_name(edge.destination) or edge.destination not in states:
            raise InvalidProtocol(f'edge to undeclared state {edge.destination!r}')
        if not isinstance(edge.probability, Fraction) or not 0 <= edge.probability <= 1:
            raise InvalidProtocol(f'invalid probability in row {edge.source!r}')
        totals[edge.source] += edge.probability
    for state, total in totals.items():
        if total != 1:
            raise InvalidProtocol(f'outgoing probabilities for {state!r} must sum to 1')
