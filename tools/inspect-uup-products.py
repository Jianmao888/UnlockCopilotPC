"""Read UUP products in one read transaction; optionally create a SQLite backup.

Never changes the live database or its ACL. Live WAL support/permissions are the
responsibility of SQLite/Windows, and errors are reported rather than bypassed.
"""
import argparse
import json
import pathlib
import sqlite3

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--database', type=pathlib.Path,
                    default=pathlib.Path(r'C:\ProgramData\Microsoft\Windows\AppRepository\StateRepository-Machine.srd'))
parser.add_argument('--backup', type=pathlib.Path)
args = parser.parse_args()
try:
    database = args.database.resolve(strict=True)
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=5) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        if args.backup:
            destination = args.backup.resolve()
            if destination == database or destination.exists():
                raise ValueError('Backup destination must be a new file')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(destination)) as backup:
                connection.backup(backup)
        connection.execute('BEGIN')
        products = [dict(row) for row in connection.execute('SELECT * FROM UupProduct ORDER BY _UupProductID')]
        relations = [dict(row) for row in connection.execute('''
            SELECT u._UupProductID, u.ProductID, u.Version,
                   p.PackageFullName, up.Flags
              FROM UupProduct u
              JOIN UupProductPackage up ON up.UupProduct=u._UupProductID
              JOIN PackageIdentity p ON p._PackageIdentityID=up.PackageIdentity
             WHERE u.ProductID LIKE 'Windows.Workload.%'
             ORDER BY u._UupProductID,p.PackageFullName''')]
        connection.rollback()
    print(json.dumps(dict(database=str(database), products=products, relations=relations),
                     ensure_ascii=False, indent=2, default=str))
except (OSError, sqlite3.Error, ValueError) as error:
    parser.exit(1, 'Read-only verification failed: ' + str(error) + '\n')
