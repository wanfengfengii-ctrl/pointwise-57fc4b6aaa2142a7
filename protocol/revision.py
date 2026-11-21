import json
import sqlite3
from decimal import Decimal
from fractions import Fraction
from os import PathLike

from protocol.model import Protocol, Revision, Transition
from protocol.validate import validate_protocol


_SCHEMA = '''
CREATE TABLE IF NOT EXISTS revisions (
    id INTEGER PRIMARY KEY,
    bench_id TEXT NOT NULL,
    snapshot TEXT NOT NULL,
    UNIQUE (bench_id, id)
);
CREATE TABLE IF NOT EXISTS current_revisions (
    bench_id TEXT PRIMARY KEY,
    revision_id INTEGER NOT NULL,
    FOREIGN KEY (bench_id, revision_id) REFERENCES revisions (bench_id, id)
);
'''


def _code(number: int) -> str:
    return f'R-{number:08d}'


def _number(revision_id: str) -> int | None:
    if not isinstance(revision_id, str) or not revision_id.startswith('R-'):
        return None
    digits = revision_id[2:]
    if not (8 <= len(digits) <= 19 and digits.isascii() and digits.isdecimal()):
        return None
    number = int(digits)
    if not 1 <= number <= 2**63 - 1 or _code(number) != revision_id:
        return None
    return number


def _snapshot(protocol: Protocol) -> str:
    return json.dumps({
        'states': protocol.states,
        'start': protocol.start,
        'pass_state': protocol.pass_state,
        'fail_state': protocol.fail_state,
        'edges': [
            (edge.source, edge.destination, str(Decimal(edge.probability.numerator)),
             str(Decimal(edge.probability.denominator)))
            for edge in protocol.transitions
        ],
    }, separators=(',', ':'))


def _read_snapshot(bench_id: str, snapshot: str) -> Protocol:
    data = json.loads(snapshot)
    edges = tuple(
        Transition(source, destination, Fraction(int(Decimal(numerator)), int(Decimal(denominator))))
        for source, destination, numerator, denominator in data['edges']
    )
    return Protocol(
        bench_id, tuple(data['states']), data['start'], data['pass_state'], data['fail_state'], edges,
    )


class RevisionStore:
    def __init__(self, path: str | PathLike[str]):
        self._connection = sqlite3.connect(path)
        self._connection.execute('PRAGMA foreign_keys = ON')

    def initialize(self) -> None:
        self._connection.executescript(_SCHEMA)

    def append(self, protocol: Protocol) -> str:
        validate_protocol(protocol)
        snapshot = _snapshot(protocol)
        with self._connection:
            cursor = self._connection.execute(
                'INSERT INTO revisions (bench_id, snapshot) VALUES (?, ?)',
                (protocol.bench_id, snapshot),
            )
            revision_number = cursor.lastrowid
            self._connection.execute(
                '''INSERT INTO current_revisions (bench_id, revision_id) VALUES (?, ?)
                   ON CONFLICT (bench_id) DO UPDATE SET revision_id = excluded.revision_id''',
                (protocol.bench_id, revision_number),
            )
        return _code(revision_number)

    def get(self, revision_id: str) -> Revision | None:
        number = _number(revision_id)
        if number is None:
            return None
        row = self._connection.execute(
            'SELECT bench_id, snapshot FROM revisions WHERE id = ?', (number,),
        ).fetchone()
        if row is None:
            return None
        return Revision(revision_id, _read_snapshot(*row))

    def current(self, bench_id: str) -> str | None:
        row = self._connection.execute(
            'SELECT revision_id FROM current_revisions WHERE bench_id = ?', (bench_id,),
        ).fetchone()
        return None if row is None else _code(row[0])

    def close(self) -> None:
        self._connection.close()
