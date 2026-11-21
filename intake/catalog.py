import sqlite3
from dataclasses import dataclass
from os import PathLike

from intake.pack import Package, PackageIdentity


class PackageConflict(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AcceptedPackage:
    accepted_id: str
    package: Package


_SCHEMA = '''
CREATE TABLE IF NOT EXISTS accepted_packages (
    accepted_id TEXT PRIMARY KEY,
    package_id TEXT NOT NULL UNIQUE,
    analysis_id TEXT NOT NULL,
    bench_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    digest TEXT NOT NULL,
    body BLOB NOT NULL
)
'''


def _accepted(row: tuple) -> AcceptedPackage:
    accepted_id, package_id, analysis_id, bench_id, revision_id, digest, body = row
    return AcceptedPackage(
        accepted_id, Package(PackageIdentity(package_id, analysis_id, bench_id, revision_id, digest), body),
    )


class IntakeCatalog:
    def __init__(self, path: str | PathLike[str]):
        self._connection = sqlite3.connect(path)

    def initialize(self) -> None:
        self._connection.execute(_SCHEMA)

    def bind(self, package: Package) -> AcceptedPackage:
        """Bind a delivery after the exchange envelope has been validated."""
        identity = package.identity
        accepted_id = f'I-{identity.package_id}'
        with self._connection:
            self._connection.execute(
                '''INSERT INTO accepted_packages
                   (accepted_id, package_id, analysis_id, bench_id, revision_id, digest, body)
                   VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (package_id) DO NOTHING''',
                (accepted_id, identity.package_id, identity.analysis_id, identity.bench_id,
                 identity.revision_id, identity.digest, package.body),
            )
            original = self.get(accepted_id)
            if original is None or original.package != package:
                raise PackageConflict(f'conflicting delivery for {identity.package_id}')
        return original

    def get(self, accepted_id: str) -> AcceptedPackage | None:
        row = self._connection.execute(
            '''SELECT accepted_id, package_id, analysis_id, bench_id, revision_id, digest, body
               FROM accepted_packages WHERE accepted_id = ?''',
            (accepted_id,),
        ).fetchone()
        return None if row is None else _accepted(row)

    def close(self) -> None:
        self._connection.close()
