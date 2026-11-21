import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from os import PathLike


def connect_archive(path: str | PathLike[str]) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


@contextmanager
def archive_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    connection.execute('BEGIN IMMEDIATE')
    try:
        yield
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
