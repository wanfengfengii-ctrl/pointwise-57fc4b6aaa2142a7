from contextlib import closing
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256

from analysis import freeze
from analysis.evidence import AnalysisIdentity, FIRST_TICK, FrozenAnalysis
from analysis.first_pass import eventual_pass_mass
from analysis.process import PassageKernel
from intake import accept, pack
from intake.admit import accept as accept_package
from intake.codec import decode_body, encode_body
from intake.select import ParentSelectionError
from records import connect_archive, get, initialize_archive
from review import sign, sign_stagger
from review.stagger import best_offsets, stagger_scores
from review.sync import UnusableEvidence
from tests import HALF, ONE, ZERO, LabCase, register_fixture
import stagger_examples


TABLE = {
    'tie': (ONE, (0, 2), HALF),
    'closed': (HALF, (0, 2), HALF),
    'dead': (ZERO, (), None),
    'retry': (ONE, (2,), Fraction(1, 3)),
    'long': (ONE, (128,), ONE),
}


def _issue_example(case, station, catalog):
    return stagger_examples.issue_pair(station, catalog, case)


class StaggerExampleTests(LabCase):
    def _offline_examples(self):
        station = self.open_station()
        catalog = self.open_intake()
        parents = {case: _issue_example(case, station, catalog) for case in TABLE}
        station.close()
        catalog.close()
        return self.open_intake(), parents

    def test_table_values_and_reopen(self):
        catalog, parents = self._offline_examples()
        archive_path = self.directory / 'archive.sqlite'
        with closing(connect_archive(archive_path)) as archive:
            initialize_archive(archive)
            signed = {case: sign_stagger(catalog, archive, *pair)
                      for case, pair in parents.items()}
            for case, (joint, offsets, conditional) in TABLE.items():
                report = signed[case]
                self.assertTrue(report.report_id.startswith('SG-'))
                self.assertEqual(
                    (report.draft.joint_pass, report.draft.offsets, report.draft.conditional_sync),
                    (joint, offsets, conditional),
                )
                self.assertEqual(tuple(p.accepted_id for p in report.draft.parents), parents[case])
                self.assertEqual(report.receipt.accepted_ids, parents[case])
                self.assertEqual(report.receipt.receipt_id, f'RC-{report.report_id}')
        catalog.close()
        with closing(connect_archive(archive_path)) as reopened:
            for case, report in signed.items():
                self.assertEqual(get(reopened, report.report_id), report)
            self.assertIsNone(get(reopened, 'SG-00000099'))
            self.assertIsNone(get(reopened, 'SR-00000099'))

    def test_swapped_parents_and_offsets(self):
        catalog, parents = self._offline_examples()
        archive = self.open_archive()
        normal = sign_stagger(catalog, archive, *parents['tie'])
        swapped = sign_stagger(catalog, archive, *parents['tie'][::-1])
        self.assertEqual(normal.draft.offsets, (0, 2))
        self.assertEqual(swapped.draft.offsets, (-2, 0))
        self.assertEqual(swapped.draft.conditional_sync, HALF)
        self.assertEqual(swapped.receipt.accepted_ids, parents['tie'][::-1])
        self.assertEqual(tuple(p.accepted_id for p in swapped.draft.parents),
                         parents['tie'][::-1])
        # Each parent keeps its own bench and identity fields.
        self.assertEqual(swapped.draft.parents[0].bench_id, '右台')
        self.assertEqual(swapped.draft.parents[1].bench_id, '左台')

    def test_empty_plan_when_no_joint_qualification(self):
        catalog, parents = self._offline_examples()
        archive = self.open_archive()
        report = sign_stagger(catalog, archive, *parents['dead'])
        self.assertEqual(report.draft.joint_pass, ZERO)
        self.assertEqual(report.draft.offsets, ())
        self.assertIsNone(report.draft.conditional_sync)
        archive.close()
        catalog.close()
        with closing(connect_archive(self.directory / 'archive.sqlite')) as reopened:
            fetched = get(reopened, report.report_id)
            self.assertEqual(fetched, report)
            self.assertEqual(fetched.draft.offsets, ())
            self.assertIsNone(fetched.draft.conditional_sync)
            self.assertEqual(
                reopened.execute('SELECT COUNT(*) FROM stagger_offsets').fetchone()[0], 0)

    def test_zero_offset_agrees_with_v1_synchronous_mass(self):
        catalog, parents = self._offline_examples()
        archive = self.open_archive()
        for case, pair in parents.items():
            with self.subTest(case=case):
                v1 = sign(catalog, archive, *pair)
                left_body = decode_body(catalog.get(pair[0]).package.body)
                right_body = decode_body(catalog.get(pair[1]).package.body)
                joint, scores = stagger_scores(left_body, right_body)
                self.assertEqual(joint, v1.draft.joint_pass)
                self.assertEqual(scores.get(0, ZERO), v1.draft.synchronous)

    def test_retry_tail_scores_match_geometric_series(self):
        catalog, parents = self._offline_examples()
        pair = parents['retry']
        left_body = decode_body(catalog.get(pair[0]).package.body)
        right_body = decode_body(catalog.get(pair[1]).package.body)
        joint, scores = stagger_scores(left_body, right_body)
        self.assertEqual(joint, ONE)
        # Left waits two ticks before its first attempt: S_2 = 1/3 is the peak,
        # and every enumerated score halves per tick away from the peak. The
        # enumeration may stop once further offsets are certified suboptimal.
        for offset, value in scores.items():
            expected = Fraction(1, 3) * HALF ** abs(offset - 2)
            self.assertEqual(value, expected)
        self.assertEqual(scores[2], Fraction(1, 3))
        self.assertEqual(best_offsets(scores), (2,))

    def test_periodic_benches_have_single_best_offset(self):
        station = self.open_station()
        catalog = self.open_intake()
        left, _ = self.issue(station, catalog, '左台', 'odd')
        right, _ = self.issue(station, catalog, '右台', 'even')
        station.close()
        catalog.close()
        catalog = self.open_intake()
        archive = self.open_archive()
        report = sign_stagger(catalog, archive, left, right)
        # The left bench passes on odd ticks, the right bench on even ticks;
        # starting the right bench one tick earlier (d = -1) aligns every attempt.
        self.assertEqual(report.draft.offsets, (-1,))
        self.assertEqual(report.draft.conditional_sync, Fraction(1, 3))

    def test_selection_and_evidence_errors_write_nothing(self):
        station = self.open_station()
        catalog = self.open_intake()
        left, _ = self.issue(station, catalog, '左台', 'retry')
        right, _ = self.issue(station, catalog, '右台', 'retry')
        same_bench, _ = self.issue(station, catalog, '左台', 'direct')
        archive = self.open_archive()
        for bad in ('I-缺件', same_bench, '   '):
            with self.subTest(bad=bad):
                with self.assertRaises(ParentSelectionError):
                    sign_stagger(catalog, archive, left, bad)
        _, frozen = freeze(station, register_fixture(station, '坏台', 'retry'))
        delivery = pack(frozen)
        body = decode_body(delivery.body)
        body['eventual_pass'], body['never_pass'] = ['0', '1'], ['1', '1']
        data = encode_body(body)
        bad_package = replace(delivery, body=data,
                              identity=replace(delivery.identity, digest=sha256(data).hexdigest()))
        bad_left = accept(catalog, bad_package, bad_package.identity)
        station.close()
        with self.assertRaisesRegex(UnusableEvidence, 'mass summary'):
            sign_stagger(catalog, archive, bad_left, right)
        for table in ('stagger_reports', 'stagger_offsets',
                      'stagger_report_parents', 'stagger_receipts'):
            self.assertEqual(archive.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)

    def test_hook_exception_rolls_back_the_whole_order(self):
        catalog, parents = self._offline_examples()
        archive_path = self.directory / 'archive.sqlite'
        with closing(connect_archive(archive_path)) as archive:
            initialize_archive(archive)
            first = sign_stagger(catalog, archive, *parents['tie'])
            pending = 'SG-00000002'

            def reject():
                self.assertEqual(
                    archive.execute('SELECT COUNT(*) FROM stagger_reports').fetchone()[0], 2)
                self.assertEqual(
                    archive.execute('SELECT COUNT(*) FROM stagger_offsets').fetchone()[0], 4)
                self.assertEqual(
                    archive.execute('SELECT COUNT(*) FROM stagger_report_parents').fetchone()[0], 4)
                self.assertEqual(
                    archive.execute('SELECT COUNT(*) FROM stagger_receipts').fetchone()[0], 2)
                with closing(connect_archive(archive_path)) as observer:
                    self.assertIsNone(get(observer, pending))
                    self.assertEqual(get(observer, first.report_id), first)
                raise RuntimeError('commit point rejected')

            with self.assertRaisesRegex(RuntimeError, 'commit point rejected'):
                sign_stagger(catalog, archive, *parents['tie'], before_commit=reject)
        with closing(connect_archive(archive_path)) as reopened:
            self.assertIsNone(get(reopened, pending))
            self.assertEqual(
                reopened.execute('SELECT COUNT(*) FROM stagger_reports').fetchone()[0], 1)
            self.assertEqual(
                reopened.execute('SELECT COUNT(*) FROM stagger_offsets').fetchone()[0], 2)
            self.assertEqual(
                reopened.execute('SELECT COUNT(*) FROM stagger_report_parents').fetchone()[0], 2)
            self.assertEqual(
                reopened.execute('SELECT COUNT(*) FROM stagger_receipts').fetchone()[0], 1)
            self.assertEqual(get(reopened, first.report_id), first)

    def test_closed_trap_with_disjoint_ticks_terminates(self):
        # A leading bench whose survivors enter a closed trap must not make the
        # enumeration run forever when every non-negative offset scores zero.
        def package(kernel, bench, revision):
            eventual = eventual_pass_mass(kernel)
            analysis = FrozenAnalysis(
                AnalysisIdentity(f'A-{revision}', bench, revision), FIRST_TICK,
                eventual, 1 - eventual, kernel)
            return pack(analysis)

        catalog = self.open_intake()
        # Left: half pass on tick 1, half trapped forever.
        left_kernel = PassageKernel(
            0,
            (((1, HALF),), ((1, ONE),)),
            (HALF, ZERO),
        )
        # Right: deterministic pass on tick 3 (0 -> 1 -> 2 -> pass).
        right_kernel = PassageKernel(
            0,
            (((1, ONE),), ((2, ONE),), ()),
            (ZERO, ZERO, ONE),
        )
        left_pkg = package(left_kernel, '左台', 'R-TRAP-L')
        right_pkg = package(right_kernel, '右台', 'R-TRAP-R')
        left = accept_package(catalog, left_pkg, left_pkg.identity)
        right = accept_package(catalog, right_pkg, right_pkg.identity)
        catalog.close()
        catalog = self.open_intake()
        archive = self.open_archive()
        report = sign_stagger(catalog, archive, left, right)
        self.assertEqual(report.draft.joint_pass, HALF)
        self.assertEqual(report.draft.offsets, (-2,))
        self.assertEqual(report.draft.conditional_sync, ONE)

    def test_v1_reports_remain_readable_alongside_stagger_reports(self):
        catalog, parents = self._offline_examples()
        archive = self.open_archive()
        v1 = sign(catalog, archive, *parents['tie'])
        stagger = sign_stagger(catalog, archive, *parents['tie'])
        self.assertNotEqual(v1.report_id, stagger.report_id)
        self.assertEqual(get(archive, v1.report_id), v1)
        self.assertEqual(get(archive, stagger.report_id), stagger)
        self.assertEqual(get(archive, v1.report_id).draft.conditional_sync, HALF)
        self.assertEqual(get(archive, stagger.report_id).draft.conditional_sync, HALF)
