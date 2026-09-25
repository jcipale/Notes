#!/usr/bin/env python3
"""
musica_db_debug.py — Portable DB inspection tool for Musica (SQLite)

No sqlite3 CLI dependency. Uses Python sqlite3.
Database path is obtained from the installed musica.conf.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


# Locate the installed Musica configuration.
SCRIPT_DIR = Path(__file__).resolve().parent
MUSICA_CONFIG_FILE = SCRIPT_DIR.parent / "config" / "musica.conf"

# Populated from musica.conf.
DB_FILE = None


def load_config():
    global DB_FILE

    if not MUSICA_CONFIG_FILE.exists():
        print(f"ERROR: Musica configuration not found: {MUSICA_CONFIG_FILE}")
        raise SystemExit(1)

    config = {}

    try:
        with MUSICA_CONFIG_FILE.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()

                if not line or line.startswith("#"):
                    continue

                if "=" not in line:
                    continue

                key, value = line.split("=", 1)

                key = key.strip()
                value = value.strip()

                if "#" in value:
                    value = value.split("#", 1)[0].rstrip()

                if ";" in value:
                    value = value.split(";", 1)[0].rstrip()

                config[key] = value

    except OSError as e:
        print(f"ERROR: Unable to read configuration: {e}")
        raise SystemExit(1)

    if "MUSICA_BASE_DIR" not in config:
        print("ERROR: MUSICA_BASE_DIR is missing from musica.conf")
        raise SystemExit(1)

    if "MUSICA_DB_FILE" not in config:
        print("ERROR: MUSICA_DB_FILE is missing from musica.conf")
        raise SystemExit(1)

    base_dir = Path(config["MUSICA_BASE_DIR"])

    db_file = config["MUSICA_DB_FILE"]
    db_file = db_file.replace("${MUSICA_BASE_DIR}", str(base_dir))

    DB_FILE = Path(db_file)


def connect_ro() -> sqlite3.Connection:
    if not DB_FILE.exists():
        raise SystemExit(f"ERROR: DB file not found: {DB_FILE}")

    uri = f"file:{DB_FILE.as_posix()}?mode=ro"

    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")

    return conn


def list_objects(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT type, name FROM sqlite_master "
        "WHERE type IN ('table','view','trigger') AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type, name"
    ).fetchall()

    tables = [r["name"] for r in rows if r["type"] == "table"]
    views = [r["name"] for r in rows if r["type"] == "view"]
    triggers = [r["name"] for r in rows if r["type"] == "trigger"]

    return tables, views, triggers


def show_schema(conn: sqlite3.Connection, name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name=? AND sql IS NOT NULL",
        (name,),
    ).fetchone()

    if not row:
        raise SystemExit(f"ERROR: No schema SQL found for object: {name}")

    return row["sql"]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Inspect Musica SQLite DB (portable debug tool)"
    )

    ap.add_argument(
        "--schema",
        metavar="OBJECT",
        help="Print CREATE SQL for a table/view/trigger name"
    )

    ap.add_argument(
        "--list",
        action="store_true",
        help="List tables/views/triggers (default behavior)"
    )

    args = ap.parse_args()

    load_config()

    print("Musica DB Debug")
    print("---------------")
    print("DB file:", DB_FILE)

    # Print sqlite library version (from Python module)
    print("sqlite3 lib:", sqlite3.sqlite_version)

    conn = connect_ro()

    try:
        # integrity check
        r = conn.execute("PRAGMA integrity_check;").fetchone()
        print("integrity_check:", (r[0] if r else "UNKNOWN"))

        # schema_version (if present)
        sv = None

        try:
            row = conn.execute(
                "SELECT value FROM musica_meta WHERE key='schema_version'"
            ).fetchone()

            sv = row["value"] if row else None

        except Exception:
            sv = None

        print(
            "schema_version:",
            sv if sv is not None else "(missing)"
        )

        tables, views, triggers = list_objects(conn)

        if args.schema:
            print("\n.schema", args.schema)
            print(show_schema(conn, args.schema).strip() + ";")
            return

        # default: list objects
        if args.list or True:
            print("\nTables:")

            for t in tables:
                print("  ", t)

            print("\nViews:")

            for v in views:
                print("  ", v)

            print("\nTriggers:")

            for tr in triggers:
                print("  ", tr)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
