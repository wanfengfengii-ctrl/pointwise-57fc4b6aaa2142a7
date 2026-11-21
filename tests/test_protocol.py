from fractions import Fraction

from analysis import freeze
from analysis.first_pass import first_hit_mass
from analysis.linear import SingularSystem, solve_exact
from analysis.process import build_process
from protocol import Transition, revise
from protocol.validate import InvalidProtocol
from tests import HALF, ONE, ZERO, LabCase, register_fixture


class ProtocolTests(LabCase):
    def test_single_pass_metrics(self):
        station = self.open_station()
        revision_id = register_fixture(station, '左台', 'fail')
        metrics, frozen = freeze(station, revision_id)
        self.assertEqual((metrics.first_tick_pass, metrics.eventual_pass, metrics.never_pass),
                         (HALF, HALF, HALF))
        process = build_process(station.get(revision_id))
        self.assertEqual(process.direct_fail, (HALF,))
        self.assertEqual(first_hit_mass(frozen.passage, 1), HALF)
        self.assertEqual(first_hit_mass(frozen.passage, 2), ZERO)

    def test_closed_branch(self):
        station = self.open_station()
        revision = register_fixture(station, '闭环台', 'closed')
        metrics, frozen = freeze(station, revision)
        self.assertEqual((metrics.first_tick_pass, metrics.eventual_pass, metrics.never_pass),
                         (HALF, HALF, HALF))
        self.assertEqual(first_hit_mass(frozen.passage, 1), HALF)
        self.assertEqual(first_hit_mass(frozen.passage, 2), ZERO)
        self.assertEqual(first_hit_mass(frozen.passage, 30), ZERO)

    def test_unknown_revision(self):
        station = self.open_station()
        with self.assertRaises(KeyError):
            freeze(station, 'R-00000099')
        self.assertIsNone(station.current('空台'))
        self.assertIsNone(station.get('R-00000099'))

    def test_invalid_mass_keeps_revision(self):
        station = self.open_station()
        old = register_fixture(station, '左台', 'fail')
        original = station.get(old)
        edge_weight = Fraction(3, 4)
        with self.assertRaisesRegex(InvalidProtocol, 'must sum to 1'):
            revise(station, '左台', states=('起点', '通过', '失败'), start='起点',
                   pass_state='通过', fail_state='失败', transitions=(
                       Transition('起点', '通过', edge_weight), Transition('起点', '失败', edge_weight),
                   ))
        station.close()
        reopened = self.open_station()
        self.assertEqual(reopened.current('左台'), old)
        self.assertEqual(reopened.get(old), original)
        self.assertEqual(freeze(reopened, old)[0].eventual_pass, HALF)
        self.assertIsNone(reopened.get('R-00000002'))

    def test_duplicate_and_zero_weight_edges(self):
        station = self.open_station()
        revision = revise(station, '左台', states=('起点', '通过', '失败'), start='起点',
                          pass_state='通过', fail_state='失败', transitions=(
                              Transition('起点', '通过', Fraction(1, 3)),
                              Transition('起点', '通过', Fraction(2, 3)),
                              Transition('起点', '起点', ZERO),
                          ))
        metrics, evidence = freeze(station, revision)
        self.assertEqual(metrics.first_tick_pass, ONE)
        self.assertEqual(evidence.passage.continuation, ((),))
        with self.assertRaisesRegex(ValueError, 'positive integer'):
            first_hit_mass(evidence.passage, 0)

    def test_rejects_invalid_station_rows(self):
        station = self.open_station()
        valid = (Transition('起点', '通过', ONE),)
        cases = (
            (('起点', '通过', '失败'), '通过', valid),
            (('起点', '通过', '失败'), '起点', (Transition('起点', '缺失', ONE),)),
            (('起点', '通过', '失败'), '起点', (Transition('起点', '通过', 1.0),)),
            (('起点', '通过', '失败'), '起点', valid + (Transition('通过', '通过', ZERO),)),
            (('起点', '通过', '失败', '未使用'), '起点', valid),
        )
        for states, initial, edges in cases:
            with self.subTest(states=states, initial=initial, edges=edges):
                with self.assertRaises(InvalidProtocol):
                    revise(station, '左台', states=states, start=initial,
                           pass_state='通过', fail_state='失败', transitions=edges)
        self.assertIsNone(station.current('左台'))

    def test_exact_solver_swaps_pivot_and_rejects_singular_system(self):
        result = solve_exact(((ZERO, ONE), (Fraction(2), Fraction(3))), (HALF, Fraction(2)))
        self.assertEqual(result, (Fraction(1, 4), HALF))
        with self.assertRaises(SingularSystem):
            solve_exact(((ONE, ONE), (ONE, ONE)), (ONE, ONE))
