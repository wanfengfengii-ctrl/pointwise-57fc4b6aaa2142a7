from dataclasses import dataclass
from hashlib import sha256

from analysis.evidence import FrozenAnalysis
from intake.codec import encode_body, encode_fraction


@dataclass(frozen=True, slots=True)
class PackageIdentity:
    package_id: str
    analysis_id: str
    bench_id: str
    revision_id: str
    digest: str


@dataclass(frozen=True, slots=True)
class Package:
    identity: PackageIdentity
    body: bytes


def pack(analysis: FrozenAnalysis) -> Package:
    origin = analysis.identity
    package_id = f'P-{origin.analysis_id}'
    kernel = analysis.passage
    body = encode_body({
        'package_id': package_id,
        'analysis_id': origin.analysis_id,
        'bench_id': origin.bench_id,
        'revision_id': origin.revision_id,
        'first_tick': analysis.first_tick,
        'eventual_pass': encode_fraction(analysis.eventual_pass),
        'never_pass': encode_fraction(analysis.never_pass),
        'passage': {
            'initial': kernel.initial,
            'continuation': [
                [[target, encode_fraction(weight)] for target, weight in row]
                for row in kernel.continuation
            ],
            'direct_pass': [encode_fraction(weight) for weight in kernel.direct_pass],
        },
    })
    return Package(
        PackageIdentity(package_id, origin.analysis_id, origin.bench_id, origin.revision_id,
                        sha256(body).hexdigest()),
        body,
    )
