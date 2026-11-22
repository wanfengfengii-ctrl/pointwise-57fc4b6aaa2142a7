from intake.catalog import AcceptedPackage
from intake.codec import PackageFormatError, decode_body, decode_fraction
from intake.select import SelectedPair
from records.schema import ParentReference, StaggerReportDraft
from review.stagger import best_offsets, stagger_scores
from review.sync import UnusableEvidence


def _reference(accepted: AcceptedPackage) -> ParentReference:
    identity = accepted.package.identity
    return ParentReference(
        accepted.accepted_id, identity.package_id, identity.bench_id, identity.revision_id,
        identity.analysis_id, identity.digest,
    )


def build_stagger_report(pair: SelectedPair) -> StaggerReportDraft:
    try:
        left = decode_body(pair.left.package.body)
        right = decode_body(pair.right.package.body)
        decode_fraction(left.get('eventual_pass'))
        decode_fraction(right.get('eventual_pass'))
    except PackageFormatError as exc:
        raise UnusableEvidence('cannot read the selected evidence') from exc
    joint, scores = stagger_scores(left, right)
    offsets = best_offsets(scores)
    if joint == 0:
        conditional = None
    else:
        top = scores[offsets[0]]
        conditional = top / joint
    return StaggerReportDraft(joint, offsets, conditional,
                              (_reference(pair.left), _reference(pair.right)))
