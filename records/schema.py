import sqlite3
from dataclasses import dataclass
from fractions import Fraction

from intake.codec import decode_fraction, encode_fraction
from records.connection import archive_transaction


@dataclass(frozen=True, slots=True)
class ParentReference:
    accepted_id: str
    package_id: str
    bench_id: str
    revision_id: str
    analysis_id: str
    digest: str


@dataclass(frozen=True, slots=True)
class ReportDraft:
    joint_pass: Fraction
    synchronous: Fraction
    conditional_sync: Fraction | None
    parents: tuple[ParentReference, ParentReference]

    def __post_init__(self) -> None:
        if not isinstance(self.joint_pass, Fraction) or not isinstance(self.synchronous, Fraction):
            raise ValueError('probability fields must be exact fractions')
        if not 0 <= self.synchronous <= self.joint_pass <= 1:
            raise ValueError('invalid report masses')
        if (self.conditional_sync is None) != (self.joint_pass == 0):
            raise ValueError('conditional probability is empty exactly when joint passage is zero')
        if self.conditional_sync is not None and (
            not isinstance(self.conditional_sync, Fraction) or not 0 <= self.conditional_sync <= 1
        ):
            raise ValueError('invalid conditional probability')
        if not isinstance(self.parents, tuple) or len(self.parents) != 2:
            raise ValueError('a report must have two ordered parents')
        left, right = self.parents
        if left.bench_id == right.bench_id or left.accepted_id == right.accepted_id:
            raise ValueError('a report must refer to two distinct bench acceptances')


@dataclass(frozen=True, slots=True)
class StaggerReportDraft:
    joint_pass: Fraction
    offsets: tuple[int, ...]
    conditional_sync: Fraction | None
    parents: tuple[ParentReference, ParentReference]

    def __post_init__(self) -> None:
        if not isinstance(self.joint_pass, Fraction) or not 0 <= self.joint_pass <= 1:
            raise ValueError('joint passage must be an exact fraction in [0, 1]')
        if not isinstance(self.offsets, tuple) or any(type(offset) is not int for offset in self.offsets):
            raise ValueError('offsets must be a tuple of integers')
        if list(self.offsets) != sorted(self.offsets) or len(set(self.offsets)) != len(self.offsets):
            raise ValueError('offsets must be distinct and sorted ascending')
        if (self.conditional_sync is None) != (self.joint_pass == 0):
            raise ValueError('conditional probability is empty exactly when joint passage is zero')
        if self.conditional_sync is not None and (
            not isinstance(self.conditional_sync, Fraction) or not 0 <= self.conditional_sync <= 1
        ):
            raise ValueError('invalid conditional probability')
        if self.joint_pass > 0 and not self.offsets:
            raise ValueError('a qualified stagger plan needs at least one optimal offset')
        if self.joint_pass == 0 and self.offsets:
            raise ValueError('an empty stagger plan carries no offsets')
        if not isinstance(self.parents, tuple) or len(self.parents) != 2:
            raise ValueError('a report must have two ordered parents')
        left, right = self.parents
        if left.bench_id == right.bench_id or left.accepted_id == right.accepted_id:
            raise ValueError('a report must refer to two distinct bench acceptances')


_REPORTS = '''
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY,
    joint_n TEXT NOT NULL,
    joint_d TEXT NOT NULL,
    sync_n TEXT NOT NULL,
    sync_d TEXT NOT NULL,
    condition_n TEXT,
    condition_d TEXT,
    CHECK ((condition_n IS NULL) = (condition_d IS NULL))
)
'''
_PARENTS = '''
CREATE TABLE IF NOT EXISTS report_parents (
    report_id INTEGER NOT NULL REFERENCES reports (id),
    slot INTEGER NOT NULL CHECK (slot IN (0, 1)),
    accepted_id TEXT NOT NULL,
    package_id TEXT NOT NULL,
    bench_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    analysis_id TEXT NOT NULL,
    digest TEXT NOT NULL,
    PRIMARY KEY (report_id, slot)
)
'''
_RECEIPTS = '''
CREATE TABLE IF NOT EXISTS receipts (
    report_id INTEGER PRIMARY KEY REFERENCES reports (id),
    report_number TEXT NOT NULL UNIQUE,
    body BLOB NOT NULL
)
'''
_STAGGER_REPORTS = '''
CREATE TABLE IF NOT EXISTS stagger_reports (
    id INTEGER PRIMARY KEY,
    joint_n TEXT NOT NULL,
    joint_d TEXT NOT NULL,
    condition_n TEXT,
    condition_d TEXT,
    CHECK ((condition_n IS NULL) = (condition_d IS NULL))
)
'''
_STAGGER_OFFSETS = '''
CREATE TABLE IF NOT EXISTS stagger_offsets (
    report_id INTEGER NOT NULL REFERENCES stagger_reports (id),
    slot INTEGER NOT NULL,
    offset_value INTEGER NOT NULL,
    PRIMARY KEY (report_id, slot)
)
'''
_STAGGER_PARENTS = '''
CREATE TABLE IF NOT EXISTS stagger_report_parents (
    report_id INTEGER NOT NULL REFERENCES stagger_reports (id),
    slot INTEGER NOT NULL CHECK (slot IN (0, 1)),
    accepted_id TEXT NOT NULL,
    package_id TEXT NOT NULL,
    bench_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    analysis_id TEXT NOT NULL,
    digest TEXT NOT NULL,
    PRIMARY KEY (report_id, slot)
)
'''
_STAGGER_RECEIPTS = '''
CREATE TABLE IF NOT EXISTS stagger_receipts (
    report_id INTEGER PRIMARY KEY REFERENCES stagger_reports (id),
    report_number TEXT NOT NULL UNIQUE,
    body BLOB NOT NULL
)
'''


def initialize_archive(connection: sqlite3.Connection) -> None:
    with archive_transaction(connection):
        for definition in (_REPORTS, _PARENTS, _RECEIPTS, _STAGGER_REPORTS,
                           _STAGGER_OFFSETS, _STAGGER_PARENTS, _STAGGER_RECEIPTS):
            connection.execute(definition)


def encode_probability(value: Fraction | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    numerator, denominator = encode_fraction(value)
    return numerator, denominator


def decode_probability(numerator: str | None, denominator: str | None) -> Fraction | None:
    if numerator is None and denominator is None:
        return None
    return decode_fraction([numerator, denominator])
