from fractions import Fraction

from analysis.evidence import FIRST_TICK
from analysis.first_pass import eventual_pass_mass
from analysis.process import PassageKernel
from intake.codec import PackageFormatError, decode_fraction


class UnusableEvidence(ValueError):
    pass


def _read_row(raw: object, size: int, direct: Fraction) -> tuple[tuple[int, Fraction], ...]:
    if not isinstance(raw, list):
        raise UnusableEvidence('invalid continuation row')
    row = []
    previous = -1
    remaining = 1 - direct
    for edge in raw:
        if not isinstance(edge, list) or len(edge) != 2:
            raise UnusableEvidence('invalid continuation edge')
        target, encoded = edge
        if type(target) is not int or not previous < target < size:
            raise UnusableEvidence('continuation targets must be distinct, ordered indices')
        weight = decode_fraction(encoded)
        if weight <= 0 or weight > remaining:
            raise UnusableEvidence('continuation and passage exceed available probability')
        remaining -= weight
        row.append((target, weight))
        previous = target
    return tuple(row)


def read_passage(body: dict) -> PassageKernel:
    if type(body.get('first_tick')) is not int or body['first_tick'] != FIRST_TICK:
        raise UnusableEvidence('passage evidence has a different time origin')
    data = body.get('passage')
    if not isinstance(data, dict) or data.keys() != {'initial', 'continuation', 'direct_pass'}:
        raise UnusableEvidence('missing or malformed passage evidence')
    initial, rows, passes = data['initial'], data['continuation'], data['direct_pass']
    if not isinstance(rows, list) or not isinstance(passes, list) or len(rows) != len(passes):
        raise UnusableEvidence('inconsistent passage dimensions')
    if type(initial) is not int or not 0 <= initial < len(rows):
        raise UnusableEvidence('anonymous initial index is out of range')
    try:
        direct_pass = tuple(decode_fraction(value) for value in passes)
        if any(not 0 <= weight <= 1 for weight in direct_pass):
            raise UnusableEvidence('invalid direct passage probability')
        kernel = PassageKernel(initial, tuple(_read_row(row, len(rows), direct)
                                             for row, direct in zip(rows, direct_pass)), direct_pass)
        passed = decode_fraction(body.get('eventual_pass'))
        never = decode_fraction(body.get('never_pass'))
    except PackageFormatError as exc:
        raise UnusableEvidence('malformed fraction in passage evidence') from exc
    if passed + never != 1 or eventual_pass_mass(kernel) != passed:
        raise UnusableEvidence('passage process disagrees with its mass summary')
    return kernel


def _product(left: PassageKernel, right: PassageKernel) -> PassageKernel:
    initial_pair = (left.initial, right.initial)
    order = [initial_pair]
    indices = {initial_pair: 0}
    continuation = []
    direct_pass = []
    for left_state, right_state in order:
        direct_pass.append(left.direct_pass[left_state] * right.direct_pass[right_state])
        row = []
        for left_target, left_weight in left.continuation[left_state]:
            for right_target, right_weight in right.continuation[right_state]:
                target_pair = (left_target, right_target)
                if target_pair not in indices:
                    indices[target_pair] = len(order)
                    order.append(target_pair)
                row.append((indices[target_pair], left_weight * right_weight))
        continuation.append(tuple(sorted(row)))
    return PassageKernel(0, tuple(continuation), tuple(direct_pass))


def synchronous_mass(left_body: dict, right_body: dict) -> Fraction:
    left = read_passage(left_body)
    right = read_passage(right_body)
    return eventual_pass_mass(_product(left, right))
