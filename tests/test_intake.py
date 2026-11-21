from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from hashlib import sha256
from threading import Barrier

from analysis import freeze
from intake import IntakeCatalog, accept, pack
from intake.admit import InvalidPackage
from intake.catalog import PackageConflict
from intake.codec import decode_body, encode_body
from tests import LabCase, register_fixture


def repack(original, body):
    data = encode_body(body)
    return replace(original, body=data, identity=replace(original.identity, digest=sha256(data).hexdigest()))


class IntakeTests(LabCase):
    def setUp(self):
        super().setUp()
        station = self.open_station()
        revision = register_fixture(station, '左台', 'retry')
        _, frozen = freeze(station, revision)
        self.package = pack(frozen)
        station.close()

    def test_duplicate_and_conflict(self):
        intake = self.open_intake()
        accepted = accept(intake, self.package, self.package.identity)
        self.assertEqual(accept(intake, self.package, self.package.identity), accepted)
        body = decode_body(self.package.body)
        body['passage']['direct_pass'] = [['3', '4']]
        body['passage']['continuation'] = [[[0, ['1', '4']]]]
        alternate = repack(self.package, body)
        self.assertNotEqual(alternate.body, self.package.body)
        self.assertNotEqual(alternate.identity.digest, self.package.identity.digest)
        with self.assertRaises(PackageConflict):
            accept(intake, alternate, alternate.identity)
        intake.close()
        reopened = self.open_intake()
        self.assertEqual(reopened.get(accepted).package, self.package)
        self.assertEqual(accept(reopened, self.package, self.package.identity), accepted)

    def test_wrong_binding(self):
        intake = self.open_intake()
        wrong_identity = replace(self.package.identity, revision_id='R-00000099')
        mismatched_body = replace(self.package, identity=wrong_identity)
        parsed = decode_body(self.package.body)
        bad_origin = repack(self.package, {**parsed, 'first_tick': 2})
        bad_summary = repack(self.package, {**parsed, 'never_pass': ['1', '2']})
        noncanonical = self.package.body + b' '
        bad_bytes = replace(self.package, body=noncanonical,
                            identity=replace(self.package.identity, digest=sha256(noncanonical).hexdigest()))
        malformed = replace(self.package, body=b'{')
        cases = ((self.package, wrong_identity), (mismatched_body, wrong_identity),
                 (bad_origin, bad_origin.identity), (bad_summary, bad_summary.identity),
                 (bad_bytes, bad_bytes.identity), (malformed, malformed.identity))
        for package, identity in cases:
            with self.subTest(package=package):
                with self.assertRaises(InvalidPackage):
                    accept(intake, package, identity)
        self.assertIsNone(intake.get(f'I-{self.package.identity.package_id}'))

    def test_concurrent_repeat_preserves_one_binding(self):
        intake = self.open_intake()
        ready = Barrier(2)

        def deliver():
            with closing(IntakeCatalog(self.directory / 'intake.sqlite')) as session:
                ready.wait(timeout=5)
                return accept(session, self.package, self.package.identity)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(deliver)
            second = pool.submit(deliver)
            first_id, second_id = first.result(timeout=10), second.result(timeout=10)
        self.assertEqual(first_id, second_id)
        self.assertEqual(intake.get(first_id).package, self.package)
