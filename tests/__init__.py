from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from analysis import freeze
from intake import IntakeCatalog, accept, pack
from protocol import RevisionStore, Transition, revise
from records import connect_archive, initialize_archive


HALF = Fraction(1, 2)
ONE = Fraction(1)
ZERO = Fraction(0)


def register_fixture(station, bench, mode):
    attempt, wait, passed, failed = ('内部台架-047-尝试', '内部台架-047-等待', '通过', '失败')
    states = [passed, attempt, failed]
    start = attempt
    if mode == 'direct':
        edges = [(attempt, passed, ONE)]
    elif mode == 'delay':
        states.insert(0, wait)
        edges = [(attempt, wait, ONE), (wait, passed, ONE)]
    elif mode == 'retry':
        edges = [(attempt, passed, HALF), (attempt, attempt, HALF)]
    elif mode in ('odd', 'even'):
        states.insert(0, wait)
        edges = [(attempt, passed, HALF), (attempt, wait, HALF), (wait, attempt, ONE)]
        if mode == 'even':
            start = wait
    elif mode == 'closed':
        states.insert(0, wait)
        edges = [(attempt, passed, HALF), (attempt, wait, HALF), (wait, wait, ONE)]
    elif mode == 'dead':
        edges = [(attempt, attempt, ONE), (attempt, passed, ZERO)]
    elif mode == 'fail':
        edges = [(attempt, passed, HALF), (attempt, failed, HALF)]
    else:
        raise ValueError(f'unknown fixture mode {mode!r}')
    return revise(station, bench, states=states, start=start, pass_state=passed, fail_state=failed,
                  transitions=map(lambda edge: Transition(*edge), edges))


class LabCase(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def open_station(self):
        station = RevisionStore(self.directory / 'station.sqlite')
        self.addCleanup(station.close)
        station.initialize()
        return station

    def open_intake(self):
        intake = IntakeCatalog(self.directory / 'intake.sqlite')
        self.addCleanup(intake.close)
        intake.initialize()
        return intake

    def open_archive(self):
        archive = connect_archive(self.directory / 'archive.sqlite')
        self.addCleanup(archive.close)
        initialize_archive(archive)
        return archive

    def issue(self, station, intake, bench, mode):
        revision = register_fixture(station, bench, mode)
        _, analysis = freeze(station, revision)
        package = pack(analysis)
        return accept(intake, package, package.identity), revision

    def offline_pair(self, left_mode, right_mode):
        intake = self.open_intake()
        station = self.open_station()
        left_id, _ = self.issue(station, intake, '左台', left_mode)
        right_id, _ = self.issue(station, intake, '右台', right_mode)
        station.close()
        intake.close()
        return self.open_intake(), left_id, right_id
