from fractions import Fraction

from analysis import freeze
from analysis.first_pass import first_hit_mass
from intake import accept, pack
from intake.codec import decode_body
from intake.select import ParentSelectionError
from records import get
from review import sign
from review.sync import UnusableEvidence, read_passage
from tests import HALF, ONE, ZERO, LabCase, register_fixture
from tests.test_intake import repack


class ReviewTests(LabCase):
    def test_geometric_sync_offline(self):
        intake, left, right = self.offline_pair('retry', 'retry')
        archive = self.open_archive()
        signed = sign(intake, archive, left, right)
        self.assertEqual((signed.draft.joint_pass, signed.draft.synchronous, signed.draft.conditional_sync),
                         (ONE, Fraction(1, 3), Fraction(1, 3)))
        self.assertEqual(signed.receipt.accepted_ids, (left, right))
        self.assertEqual(get(archive, signed.report_id), signed)

    def test_offline_evidence(self):
        intake, left, right = self.offline_pair('retry', 'retry')
        for accepted_id in (left, right):
            accepted = intake.get(accepted_id)
            body = decode_body(accepted.package.body)
            self.assertEqual(set(body), {'package_id', 'analysis_id', 'bench_id', 'revision_id',
                                         'first_tick', 'eventual_pass', 'never_pass', 'passage'})
            self.assertEqual(set(body['passage']), {'initial', 'continuation', 'direct_pass'})
            self.assertNotIn('内部台架-047', str(body))
            process = read_passage(body)
            self.assertEqual((first_hit_mass(process, 1), first_hit_mass(process, 2)),
                             (HALF, Fraction(1, 4)))
        result = sign(intake, self.open_archive(), left, right)
        self.assertEqual(result.draft.conditional_sync, Fraction(1, 3))

    def test_partial_pass(self):
        intake, left, right = self.offline_pair('closed', 'retry')
        result = sign(intake, self.open_archive(), left, right)
        self.assertEqual((result.draft.joint_pass, result.draft.synchronous, result.draft.conditional_sync),
                         (HALF, Fraction(1, 4), HALF))

    def test_disjoint_first_passages(self):
        intake, left, right = self.offline_pair('direct', 'delay')
        result = sign(intake, self.open_archive(), left, right)
        self.assertEqual(result.draft.joint_pass, ONE)
        self.assertEqual(result.draft.conditional_sync, ZERO)
        self.assertIsInstance(result.draft.conditional_sync, Fraction)

    def test_periodic_miss(self):
        intake, left, right = self.offline_pair('odd', 'even')
        result = sign(intake, self.open_archive(), left, right)
        self.assertEqual((result.draft.joint_pass, result.draft.synchronous, result.draft.conditional_sync),
                         (ONE, ZERO, ZERO))

    def test_invalid_pair(self):
        station = self.open_station()
        intake = self.open_intake()
        left, _ = self.issue(station, intake, '左台', 'direct')
        same_bench, _ = self.issue(station, intake, '左台', 'delay')
        station.close()
        archive = self.open_archive()
        for right in ('I-缺件', same_bench):
            with self.subTest(right=right):
                with self.assertRaises(ParentSelectionError):
                    sign(intake, archive, left, right)
        self.assertEqual(archive.execute('SELECT COUNT(*) FROM reports').fetchone()[0], 0)
        self.assertEqual(archive.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 0)

    def test_inconsistent_passage_cannot_be_signed(self):
        station = self.open_station()
        intake = self.open_intake()
        _, frozen = freeze(station, register_fixture(station, '左台', 'retry'))
        delivery = pack(frozen)
        body = decode_body(delivery.body)
        body['eventual_pass'], body['never_pass'] = ['0', '1'], ['1', '1']
        bad = repack(delivery, body)
        left = accept(intake, bad, bad.identity)
        right, _ = self.issue(station, intake, '右台', 'retry')
        station.close()
        archive = self.open_archive()
        with self.assertRaisesRegex(UnusableEvidence, 'disagrees with its mass summary'):
            sign(intake, archive, left, right)
        self.assertEqual(archive.execute('SELECT COUNT(*) FROM reports').fetchone()[0], 0)
        self.assertEqual(archive.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 0)

    def test_no_common_pass(self):
        intake, left, right = self.offline_pair('dead', 'retry')
        archive = self.open_archive()
        result = sign(intake, archive, left, right)
        self.assertEqual((result.draft.joint_pass, result.draft.synchronous), (ZERO, ZERO))
        self.assertIsNone(result.draft.conditional_sync)
        archive.close()
        intake.close()
        original = get(self.open_archive(), result.report_id)
        self.assertEqual(original, result)
        self.assertIsNone(original.draft.conditional_sync)
        self.assertEqual(original.receipt.accepted_ids, (left, right))
        self.assertEqual(original.receipt.receipt_id, f'RC-{result.report_id}')
