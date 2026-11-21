from hashlib import sha256

from analysis.evidence import FIRST_TICK
from intake.catalog import IntakeCatalog
from intake.codec import PackageFormatError, decode_body, decode_fraction
from intake.pack import Package, PackageIdentity


class InvalidPackage(ValueError):
    pass


def accept(catalog: IntakeCatalog, package: Package, expected: PackageIdentity) -> str:
    if not isinstance(package, Package) or not isinstance(expected, PackageIdentity):
        raise InvalidPackage('a package and expected fixed identity are required')
    identity = package.identity
    if not isinstance(identity, PackageIdentity) or identity != expected:
        raise InvalidPackage('delivery differs from expected identity')
    identifiers = {
        'package_id': identity.package_id,
        'analysis_id': identity.analysis_id,
        'bench_id': identity.bench_id,
        'revision_id': identity.revision_id,
    }
    if any(not isinstance(value, str) or not value.strip() for value in identifiers.values()):
        raise InvalidPackage('package identifiers must be nonempty text')
    try:
        for value in identifiers.values():
            value.encode('utf-8')
        body = decode_body(package.body)
        passed = decode_fraction(body.get('eventual_pass'))
        never = decode_fraction(body.get('never_pass'))
    except (PackageFormatError, UnicodeError) as exc:
        raise InvalidPackage('invalid package data') from exc
    if sha256(package.body).hexdigest() != identity.digest:
        raise InvalidPackage('body digest does not match the delivery identity')
    if any(body.get(field) != value for field, value in identifiers.items()):
        raise InvalidPackage('body identifiers do not match the delivery identity')
    if type(body.get('first_tick')) is not int or body['first_tick'] != FIRST_TICK:
        raise InvalidPackage('invalid first tick')
    if not 0 <= passed <= 1 or not 0 <= never <= 1 or passed + never != 1:
        raise InvalidPackage('invalid passage mass summary')
    return catalog.bind(package).accepted_id
