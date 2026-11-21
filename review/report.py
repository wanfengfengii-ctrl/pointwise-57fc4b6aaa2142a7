from intake.catalog import AcceptedPackage
from intake.codec import PackageFormatError, decode_body, decode_fraction
from intake.select import SelectedPair
from records.schema import ParentReference, ReportDraft
from review.condition import conditional_sync_probability, joint_pass_probability
from review.sync import UnusableEvidence, synchronous_mass


def _reference(accepted: AcceptedPackage) -> ParentReference:
    identity = accepted.package.identity
    return ParentReference(
        accepted.accepted_id, identity.package_id, identity.bench_id, identity.revision_id,
        identity.analysis_id, identity.digest,
    )


def build_report(pair: SelectedPair) -> ReportDraft:
    try:
        left = decode_body(pair.left.package.body)
        right = decode_body(pair.right.package.body)
        left_pass = decode_fraction(left.get('eventual_pass'))
        right_pass = decode_fraction(right.get('eventual_pass'))
    except PackageFormatError as exc:
        raise UnusableEvidence('cannot read the selected evidence') from exc
    same_tick = synchronous_mass(left, right)
    joint = joint_pass_probability(left_pass, right_pass)
    condition = conditional_sync_probability(joint, same_tick)
    return ReportDraft(joint, same_tick, condition, (_reference(pair.left), _reference(pair.right)))
