import sqlite3
from collections.abc import Callable

from intake.catalog import IntakeCatalog
from intake.select import select_pair
from records.stagger_publish import PublishedStaggerReport, publish_stagger
from review.stagger_report import build_stagger_report


def sign_stagger(
    catalog: IntakeCatalog,
    archive: sqlite3.Connection,
    left_id: str,
    right_id: str,
    *,
    before_commit: Callable[[], None] | None = None,
) -> PublishedStaggerReport:
    pair = select_pair(catalog, left_id, right_id)
    draft = build_stagger_report(pair)
    return publish_stagger(archive, draft, before_commit=before_commit)
