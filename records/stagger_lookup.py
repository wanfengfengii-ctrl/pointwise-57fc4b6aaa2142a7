import sqlite3

from records.receipt import decode_receipt
from records.schema import ParentReference, StaggerReportDraft, decode_probability
from records.stagger_publish import PublishedStaggerReport


_READ_STAGGER = '''
SELECT r.joint_n, r.joint_d, r.condition_n, r.condition_d, receipt.body,
       lhs.accepted_id, lhs.package_id, lhs.bench_id, lhs.revision_id, lhs.analysis_id, lhs.digest,
       rhs.accepted_id, rhs.package_id, rhs.bench_id, rhs.revision_id, rhs.analysis_id, rhs.digest
FROM stagger_receipts AS receipt
JOIN stagger_reports AS r ON r.id = receipt.report_id
JOIN stagger_report_parents AS lhs ON lhs.report_id = r.id AND lhs.slot = 0
JOIN stagger_report_parents AS rhs ON rhs.report_id = r.id AND rhs.slot = 1
WHERE receipt.report_number = ?
'''

_READ_OFFSETS = '''
SELECT offset_value FROM stagger_offsets
WHERE report_id = (SELECT report_id FROM stagger_receipts WHERE report_number = ?)
ORDER BY slot
'''


def get_stagger(connection: sqlite3.Connection, report_id: str) -> PublishedStaggerReport | None:
    row = connection.execute(_READ_STAGGER, (report_id,)).fetchone()
    if row is None:
        return None
    joint = decode_probability(row[0], row[1])
    conditional = decode_probability(row[2], row[3])
    parents = ParentReference(*row[5:11]), ParentReference(*row[11:17])
    offsets = tuple(value for (value,) in connection.execute(_READ_OFFSETS, (report_id,)).fetchall())
    draft = StaggerReportDraft(joint, offsets, conditional, parents)
    return PublishedStaggerReport(report_id, draft, decode_receipt(row[4]))
