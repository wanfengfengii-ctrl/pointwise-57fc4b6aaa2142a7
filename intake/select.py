from dataclasses import dataclass

from intake.catalog import AcceptedPackage, IntakeCatalog


class ParentSelectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SelectedPair:
    left: AcceptedPackage
    right: AcceptedPackage


def select_pair(catalog: IntakeCatalog, left_id: str, right_id: str) -> SelectedPair:
    for position, accepted_id in (('left', left_id), ('right', right_id)):
        if not isinstance(accepted_id, str) or not accepted_id.strip():
            raise ParentSelectionError(f'{position} acceptance number must be nonempty text')
    left = catalog.get(left_id)
    right = catalog.get(right_id)
    if left is None:
        raise ParentSelectionError(f'unknown left acceptance {left_id!r}')
    if right is None:
        raise ParentSelectionError(f'unknown right acceptance {right_id!r}')
    if left.package.identity.bench_id == right.package.identity.bench_id:
        raise ParentSelectionError('parents must belong to distinct benches')
    return SelectedPair(left, right)
