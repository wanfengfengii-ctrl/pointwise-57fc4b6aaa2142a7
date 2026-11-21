import sqlite3
from collections.abc import Callable

from intake.catalog import IntakeCatalog
from intake.select import select_pair
from records.publish import PublishedReport, publish
from review.report import build_report


def sign(
    catalog: IntakeCatalog,
    archive: sqlite3.Connection,
    left_id: str,
    right_id: str,
    *,
    before_commit: Callable[[], None] | None = None,
) -> PublishedReport:
    pair = select_pair(catalog, left_id, right_id)
    draft = build_report(pair)
    return publish(archive, draft, before_commit=before_commit)
