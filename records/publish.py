import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from records.connection import archive_transaction
from records.receipt import Receipt, encode_receipt, make_receipt
from records.schema import ReportDraft, encode_probability


@dataclass(frozen=True, slots=True)
class PublishedReport:
    report_id: str
    draft: ReportDraft
    receipt: Receipt


def publish(
    connection: sqlite3.Connection,
    draft: ReportDraft,
    *,
    before_commit: Callable[[], None] | None = None,
) -> PublishedReport:
    encoded = (encode_probability(draft.joint_pass) + encode_probability(draft.synchronous)
               + encode_probability(draft.conditional_sync))
    left, right = draft.parents
    with archive_transaction(connection):
        cursor = connection.execute(
            '''INSERT INTO reports (joint_n, joint_d, sync_n, sync_d, condition_n, condition_d)
               VALUES (?, ?, ?, ?, ?, ?)''', encoded,
        )
        number = cursor.lastrowid
        report_id = f'SR-{number:08d}'
        connection.executemany(
            '''INSERT INTO report_parents
               (report_id, slot, accepted_id, package_id, bench_id, revision_id, analysis_id, digest)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            [(number, slot, parent.accepted_id, parent.package_id, parent.bench_id,
              parent.revision_id, parent.analysis_id, parent.digest)
             for slot, parent in enumerate(draft.parents)],
        )
        receipt = make_receipt(report_id, (left.accepted_id, right.accepted_id))
        connection.execute(
            'INSERT INTO receipts (report_id, report_number, body) VALUES (?, ?, ?)',
            (number, report_id, encode_receipt(receipt)),
        )
        if before_commit is not None:
            before_commit()
    return PublishedReport(report_id, draft, receipt)
