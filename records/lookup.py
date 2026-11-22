import sqlite3

from records.publish import PublishedReport
from records.receipt import decode_receipt
from records.schema import ParentReference, ReportDraft, decode_probability
from records.stagger_lookup import get_stagger


RetrievedReport = PublishedReport


_READ_REPORT = '''
SELECT r.joint_n, r.joint_d, r.sync_n, r.sync_d, r.condition_n, r.condition_d, receipt.body,
       lhs.accepted_id, lhs.package_id, lhs.bench_id, lhs.revision_id, lhs.analysis_id, lhs.digest,
       rhs.accepted_id, rhs.package_id, rhs.bench_id, rhs.revision_id, rhs.analysis_id, rhs.digest
FROM receipts AS receipt
JOIN reports AS r ON r.id = receipt.report_id
JOIN report_parents AS lhs ON lhs.report_id = r.id AND lhs.slot = 0
JOIN report_parents AS rhs ON rhs.report_id = r.id AND rhs.slot = 1
WHERE receipt.report_number = ?
'''


def get(connection: sqlite3.Connection, report_id: str) -> RetrievedReport | None:
    if isinstance(report_id, str) and report_id.startswith('SG-'):
        return get_stagger(connection, report_id)
    row = connection.execute(_READ_REPORT, (report_id,)).fetchone()
    if row is None:
        return None
    joint = decode_probability(row[0], row[1])
    synchronous = decode_probability(row[2], row[3])
    conditional = decode_probability(row[4], row[5])
    parents = ParentReference(*row[7:13]), ParentReference(*row[13:19])
    draft = ReportDraft(joint, synchronous, conditional, parents)
    return RetrievedReport(report_id, draft, decode_receipt(row[6]))
