from contextlib import closing
from fractions import Fraction

from analysis import freeze
from intake import accept, pack
from protocol import Transition, revise
from records import connect_archive, get, initialize_archive
from review import sign
from tests import ONE, ZERO, LabCase


class RecordsTests(LabCase):
    def test_revision_and_reopen(self):
        station = self.open_station()
        intake = self.open_intake()
        right, right_revision = self.issue(station, intake, '右台', 'direct')
        left, left_revision = self.issue(station, intake, '左台', 'direct')
        self.assertGreater(left, right)
        station.close()
        archive = self.open_archive()
        original = sign(intake, archive, left, right)
        station = self.open_station()
        new_left, new_revision = self.issue(station, intake, '左台', 'delay')
        self.assertEqual(station.current('左台'), new_revision)
        self.assertIsNotNone(station.get(left_revision))
        station.close()
        old_again = sign(intake, archive, left, right)
        changed = sign(intake, archive, new_left, right)
        self.assertEqual(original.draft.conditional_sync, ONE)
        self.assertEqual(old_again.draft, original.draft)
        self.assertEqual(changed.draft.conditional_sync, ZERO)
        self.assertEqual(tuple(parent.revision_id for parent in original.draft.parents),
                         (left_revision, right_revision))
        self.assertEqual(tuple(parent.revision_id for parent in changed.draft.parents),
                         (new_revision, right_revision))
        self.assertEqual(original.receipt.accepted_ids, (left, right))
        self.assertEqual(changed.receipt.accepted_ids, (new_left, right))
        archive.close()
        intake.close()
        reopened = self.open_archive()
        for signed in (original, old_again, changed):
            self.assertEqual(get(reopened, signed.report_id), signed)
        self.assertIsNone(get(reopened, 'SR-00000099'))

    def test_shifted_retry(self):
        intake, left, right = self.offline_pair('retry', 'retry')
        archive = self.open_archive()
        old = sign(intake, archive, left, right)
        station = self.open_station()
        new_left, new_revision = self.issue(station, intake, '左台', 'odd')
        station.close()
        new = sign(intake, archive, new_left, right)
        archive.close()
        intake.close()
        reopened = self.open_archive()
        old_retrieved = get(reopened, old.report_id)
        new_retrieved = get(reopened, new.report_id)
        self.assertEqual(old_retrieved, old)
        self.assertEqual(new_retrieved, new)
        self.assertEqual((old_retrieved.draft.conditional_sync, new_retrieved.draft.conditional_sync),
                         (Fraction(1, 3), Fraction(2, 7)))
        self.assertEqual(new_retrieved.draft.joint_pass, ONE)
        self.assertEqual(new_retrieved.draft.parents[0].revision_id, new_revision)
        self.assertEqual(old_retrieved.receipt.accepted_ids, (left, right))
        self.assertEqual(new_retrieved.receipt.accepted_ids, (new_left, right))
        self.assertEqual(new_retrieved.draft.parents[1], old_retrieved.draft.parents[1])

    def test_failed_commit(self):
        intake, left, right = self.offline_pair('retry', 'retry')
        archive = self.open_archive()
        old = sign(intake, archive, left, right)
        self.assertEqual(old.draft.conditional_sync, Fraction(1, 3))
        pending_id = 'SR-00000002'

        def fail_after_staging():
            self.assertEqual(archive.execute('SELECT COUNT(*) FROM reports').fetchone()[0], 2)
            self.assertEqual(archive.execute('SELECT COUNT(*) FROM report_parents').fetchone()[0], 4)
            self.assertEqual(archive.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 2)
            with closing(connect_archive(self.directory / 'archive.sqlite')) as observer:
                self.assertIsNone(get(observer, pending_id))
                self.assertEqual(get(observer, old.report_id), old)
            raise RuntimeError('commit point rejected')

        with self.assertRaisesRegex(RuntimeError, 'commit point rejected'):
            sign(intake, archive, left, right, before_commit=fail_after_staging)
        archive.close()
        reopened = self.open_archive()
        self.assertIsNone(get(reopened, pending_id))
        self.assertEqual(reopened.execute('SELECT COUNT(*) FROM reports').fetchone()[0], 1)
        self.assertEqual(reopened.execute('SELECT COUNT(*) FROM report_parents').fetchone()[0], 2)
        self.assertEqual(reopened.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 1)
        self.assertEqual(get(reopened, old.report_id), old)
        retry = sign(intake, reopened, left, right)
        self.assertEqual(retry.draft, old.draft)
        self.assertEqual(get(reopened, retry.report_id), retry)
        self.assertNotEqual(retry.receipt.receipt_id, old.receipt.receipt_id)

    def test_exact_reopen_and_repeated_initialization(self):
        intake, left, right = self.offline_pair('retry', 'retry')
        archive = self.open_archive()
        signed = sign(intake, archive, left, right)
        initialize_archive(archive)
        archive.close()
        original = get(self.open_archive(), signed.report_id)
        self.assertEqual(signed.draft.conditional_sync, Fraction(1, 3))
        self.assertEqual(original.draft.conditional_sync, Fraction(1, 3))
        self.assertEqual(original, signed)

    def test_archive_preserves_wide_integer_probability_parts(self):
        station = self.open_station()
        intake = self.open_intake()
        chance = Fraction(1, 2**100 + 7)
        revision = revise(station, '左台', states=('试', '过', '败'), start='试',
                          pass_state='过', fail_state='败', transitions=(
                              Transition('试', '过', chance), Transition('试', '败', 1 - chance),
                          ))
        _, frozen = freeze(station, revision)
        package = pack(frozen)
        left = accept(intake, package, package.identity)
        right, _ = self.issue(station, intake, '右台', 'direct')
        station.close()
        archive = self.open_archive()
        signed = sign(intake, archive, left, right)
        archive.close()
        original = get(self.open_archive(), signed.report_id)
        self.assertEqual((original.draft.joint_pass, original.draft.synchronous,
                          original.draft.conditional_sync), (chance, chance, ONE))
