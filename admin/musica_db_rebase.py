#!/usr/bin/env python3

"""
Musica V1 -> V1.1 database rebase utility.

Usage:
    musica_db_rebase.py <path-to-musica.db>

The database path is supplied by the user.  The script does not attempt
to locate a Musica installation.

The rebase rebuilds the recordings table so the genre CHECK constraint
supports the V1.1 genres while preserving all existing records and IDs.
A timestamped backup is created before any modification.
"""

import os
import shutil
import sqlite3
import sys
from datetime import datetime


V11_GENRES = (
    "Jazz",
    "Rock",
    "Country",
    "Classical",
    "Symphonic",
    "Soundtrack",
)

EXPECTED_COLUMNS = [
    "id",
    "artist",
    "title",
    "year",
    "composer",
    "orchestra",
    "conductor",
    "genre",
    "format",
    "label",
    "catalog_number",
    "recording_mode",
    "reissue",
    "dbx_encoded",
]


def usage():
    print(f"Usage: {os.path.basename(sys.argv[0])} <path-to-musica.db>")


def database_is_current(connection):
    """Return True if the recordings table already has the V1.1 genre rule."""

    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'recordings'
        """
    ).fetchone()

    if row is None or row[0] is None:
        return False

    table_sql = row[0]

    if "Classical" not in table_sql:
        return False

    if "Soundtrack" not in table_sql:
        return False

    # The index is a separate sqlite_master object.  Do not look for
    # its name in the CREATE TABLE statement.
    index_row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'index'
          AND name = 'idx_recordings_artist_title_year'
        """
    ).fetchone()

    if index_row is None:
        return False

    return True


def get_columns(connection):
    rows = connection.execute("PRAGMA table_info(recordings)").fetchall()
    return [row[1] for row in rows]


def create_rebased_table(connection):
    connection.execute(
        """
        CREATE TABLE recordings_rebase (
            id INTEGER PRIMARY KEY,
            artist TEXT NOT NULL,
            title TEXT NOT NULL,

            year INTEGER NOT NULL
                CHECK (year >= 1900),

            composer TEXT,
            orchestra TEXT,
            conductor TEXT,

            genre TEXT NOT NULL
                CHECK (
                    genre IN (
                        'Jazz',
                        'Rock',
                        'Country',
                        'Classical',
                        'Symphonic',
                        'Soundtrack'
                    )
                ),

            format TEXT NOT NULL
                CHECK (
                    format IN (
                        'LP',
                        'CD',
                        'Cass',
                        'RtR',
                        '78',
                        '4T',
                        '8T'
                    )
                ),

            label TEXT,
            catalog_number TEXT,

            recording_mode TEXT
                CHECK (recording_mode IN ('M', 'S', 'B')),

            reissue TEXT
                CHECK (reissue IN ('Y', 'N')),

            dbx_encoded TEXT
                CHECK (dbx_encoded IN ('Y'))
        )
        """
    )


def create_index_and_triggers(connection):
    connection.execute(
        """
        CREATE INDEX idx_recordings_artist_title_year
        ON recordings (artist, title, year)
        """
    )

    connection.execute(
        """
        DROP TRIGGER IF EXISTS trg_recordings_year_ins
        """
    )

    connection.execute(
        """
        CREATE TRIGGER trg_recordings_year_ins
        BEFORE INSERT ON recordings
        FOR EACH ROW
        WHEN NEW.year > (CAST(strftime('%Y','now') AS INTEGER) + 1)
        BEGIN
          SELECT RAISE(ABORT, 'Invalid year: exceeds allowed range');
        END
        """
    )

    connection.execute(
        """
        DROP TRIGGER IF EXISTS trg_recordings_year_upd
        """
    )

    connection.execute(
        """
        CREATE TRIGGER trg_recordings_year_upd
        BEFORE UPDATE ON recordings
        FOR EACH ROW
        WHEN NEW.year > (CAST(strftime('%Y','now') AS INTEGER) + 1)
        BEGIN
          SELECT RAISE(ABORT, 'Invalid year: exceeds allowed range');
        END
        """
    )


def main():
    if len(sys.argv) != 2:
        usage()
        return 1

    db_path = os.path.abspath(os.path.expanduser(sys.argv[1]))

    if not os.path.isfile(db_path):
        print(f"ERROR: Database not found: {db_path}")
        return 1

    print()
    print("Musica Database Rebase")
    print("----------------------")
    print("Database:")
    print(f"  {db_path}")
    print()

    backup_path = (
        f"{db_path}.pre-rebase-"
        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )

    connection = None

    try:
        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA busy_timeout = 5000")

        table_row = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'recordings'
            """
        ).fetchone()

        if table_row is None:
            raise RuntimeError("recordings table was not found.")

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integrity != "ok":
            raise RuntimeError(
                f"Database integrity check failed: {integrity}"
            )

        if database_is_current(connection):
            print("Database is already at the V1.1 schema.")
            print("No changes were made.")
            connection.close()
            return 0

        columns = get_columns(connection)

        if columns != EXPECTED_COLUMNS:
            raise RuntimeError(
                "Database does not have the expected Musica recordings "
                "table structure."
            )

        record_count = connection.execute(
            "SELECT COUNT(*) FROM recordings"
        ).fetchone()[0]

        print(f"Records before rebase: {record_count}")
        print()

        connection.close()
        connection = None

        shutil.copy2(db_path, backup_path)

        print("Backup created:")
        print(f"  {backup_path}")
        print()

        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA busy_timeout = 5000")

        connection.execute("BEGIN IMMEDIATE")

        # Build the V1.1 table while the original recordings table
        # remains intact.
        create_rebased_table(connection)

        connection.execute(
            """
            INSERT INTO recordings_rebase (
                id,
                artist,
                title,
                year,
                composer,
                orchestra,
                conductor,
                genre,
                format,
                label,
                catalog_number,
                recording_mode,
                reissue,
                dbx_encoded
            )
            SELECT
                id,
                artist,
                title,
                year,
                composer,
                orchestra,
                conductor,
                genre,
                format,
                label,
                catalog_number,
                recording_mode,
                reissue,
                dbx_encoded
            FROM recordings
            """
        )

        copied_count = connection.execute(
            "SELECT COUNT(*) FROM recordings_rebase"
        ).fetchone()[0]

        if copied_count != record_count:
            raise RuntimeError(
                "Record count changed during rebase."
            )

        # The old index and triggers must be removed before the old
        # recordings table is removed.  This also prevents the index
        # name from colliding when it is recreated below.
        connection.execute(
            "DROP INDEX IF EXISTS idx_recordings_artist_title_year"
        )

        connection.execute(
            "DROP TRIGGER IF EXISTS trg_recordings_year_ins"
        )

        connection.execute(
            "DROP TRIGGER IF EXISTS trg_recordings_year_upd"
        )

        connection.execute(
            "DROP TABLE recordings"
        )

        connection.execute(
            "ALTER TABLE recordings_rebase RENAME TO recordings"
        )

        create_index_and_triggers(connection)

        final_count = connection.execute(
            "SELECT COUNT(*) FROM recordings"
        ).fetchone()[0]

        if final_count != record_count:
            raise RuntimeError(
                "Final record count does not match the original."
            )

        connection.commit()

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integrity != "ok":
            raise RuntimeError(
                f"Final database integrity check failed: {integrity}"
            )

        connection.close()
        connection = None

        print("REBASE SUCCESSFUL")
        print()
        print(f"Records after rebase: {final_count}")
        print(f"Backup: {backup_path}")

        return 0

    except (sqlite3.Error, OSError, RuntimeError) as error:
        if connection is not None:
            try:
                connection.rollback()
            except sqlite3.Error:
                pass
            connection.close()

        print()
        print("REBASE FAILED:")
        print(f"  {error}")
        print()
        print("The original database was not committed.")
        print(f"A pre-rebase backup exists: {backup_path}")

        return 1


if __name__ == "__main__":
    sys.exit(main())
