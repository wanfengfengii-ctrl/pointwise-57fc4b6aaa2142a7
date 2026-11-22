import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from records.connection import archive_transaction
from records.receipt import Receipt, encode_receipt, make_receipt
from records.schema import StaggerReportDraft, encode_probability


@dataclass(frozen=True, slots=True)
class PublishedStaggerReport:
    report_id: str
    draft: StaggerReportDraft
    receipt: Receipt


def publish_stagger(
    connection: sqlite3.Connection,
    draft: StaggerReportDraft,
    *,
    before_commit: Callable[[], None] | None = None,
) -> PublishedStaggerReport:
    encoded = encode_probability(draft.joint_pass) + encode_probability(draft.conditional_sync)
    left, right = draft.parents
    with archive_transaction(connection):
        cursor = connection.execute(
            '''INSERT INTO stagger_reports (joint_n, joint_d, condition_n, condition_d)
               VALUES (?, ?, ?, ?)''',
            encoded,
        )
        number = cursor.lastrowid
        report_id = f'SG-{number:08d}'
        connection.executemany(
            '''INSERT INTO stagger_offsets (report_id, slot, offset_value)
               VALUES (?, ?, ?)''',
            [(number, slot, offset) for slot, offset in enumerate(draft.offsets)],
        )
        connection.executemany(
            '''INSERT INTO stagger_report_parents
               (report_id, slot, accepted_id, package_id, bench_id, revision_id, analysis_id, digest)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            [(number, slot, parent.accepted_id, parent.package_id, parent.bench_id,
              parent.revision_id, parent.analysis_id, parent.digest)
             for slot, parent in enumerate(draft.parents)],
        )
        receipt = make_receipt(report_id, (left.accepted_id, right.accepted_id))
        connection.execute(
            'INSERT INTO stagger_receipts (report_id, report_number, body) VALUES (?, ?, ?)',
            (number, report_id, encode_receipt(receipt)),
        )
        if before_commit is not None:
            before_commit()
    return PublishedStaggerReport(report_id, draft, receipt)
