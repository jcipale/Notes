#!/usr/bin/env python3
"""
musica_db_sql_provision.py — Musica SQLite provisioning (admin utility)

Default (writes):
1) Ensure bootstrap objects exist (musica_meta, musica_users, v_musica_users, trigger)
2) Ensure current OS user exists in musica_users with role='owner'
3) Load SQLite install schema from ~/Musica/sql/install/*.sql (tables/views/triggers/indexes)
4) Stamp schema_version + provisioned_by

--check (read-only):
- PRAGMA integrity_check
- verify bootstrap objects
- verify current user row
- verify install schema objects exist (at least 'recordings')

Non-responsibilities:
- No clean-slate/reset
- No ownership enforcement/override flags
- No directory creation (installer/layout handles directories)
"""

from __future__ import annotations

import argparse
import getpass
import sqlite3
import sys
from pathlib import Path
from typing import Tuple

# Locate the installed Musica configuration.
SCRIPT_DIR = Path(__file__).resolve().parent
MUSICA_CONFIG_FILE = SCRIPT_DIR.parent / "config" / "musica.conf"

# These are populated from musica.conf.
MUSICA_BASE_DIR = None
DB_FILE = None
INSTALL_SQL_DIR = None

# Increment when you introduce real migrations
SCHEMA_VERSION = 1

# Required bootstrap objects for "provisioned" state
REQUIRED_TABLES: Tuple[str, ...] = ("musica_meta", "musica_users")
REQUIRED_VIEWS: Tuple[str, ...] = ("v_musica_users",)
REQUIRED_TRIGGERS: Tuple[str, ...] = ("trg_musica_users_username_nonempty",)

# Minimal "install schema present" signals (SQLite app schema)
REQUIRED_INSTALL_TABLES: Tuple[str, ...] = ("recordings",)
# Optional signals (warn-only)
OPTIONAL_INSTALL_TABLES: Tuple[str, ...] = ("audit_recordings", "stg_recordings")
OPTIONAL_INSTALL_VIEWS: Tuple[str, ...] = ("v_recordings_display",)

# System configuration read
def load_config() -> None:
    global MUSICA_BASE_DIR
    global DB_FILE
    global INSTALL_SQL_DIR

    if not MUSICA_CONFIG_FILE.is_file():
        raise SystemExit(
            f"ERROR: Musica configuration file not found: "
            f"{MUSICA_CONFIG_FILE}"
        )

    config = {}

    for raw in MUSICA_CONFIG_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()

        if not line or line.startswith("#") or line.startswith(";"):
            continue

        for marker in ("#", ";"):
            if marker in line:
                line = line.split(marker, 1)[0].rstrip()

        if not line:
            continue

        if "=" not in line:
            raise SystemExit(
                f"ERROR: Invalid configuration line in "
                f"{MUSICA_CONFIG_FILE}: {raw}"
            )

        key, value = line.split("=", 1)
        config[key.strip()] = value.strip()

    if "MUSICA_BASE_DIR" not in config:
        raise SystemExit(
            f"ERROR: MUSICA_BASE_DIR not found in {MUSICA_CONFIG_FILE}"
        )

    base_dir = config["MUSICA_BASE_DIR"]

    # Expand the simple ${KEY} references used by musica.conf.
    for key, value in config.items():
        config[key] = value.replace(
            "${MUSICA_BASE_DIR}",
            base_dir
        )

    if "MUSICA_DB_FILE" not in config:
        raise SystemExit(
            f"ERROR: MUSICA_DB_FILE not found in {MUSICA_CONFIG_FILE}"
        )

    if "MUSICA_SQL_DIR" not in config:
        raise SystemExit(
            f"ERROR: MUSICA_SQL_DIR not found in {MUSICA_CONFIG_FILE}"
        )

    MUSICA_BASE_DIR = Path(config["MUSICA_BASE_DIR"]).expanduser()
    DB_FILE = Path(config["MUSICA_DB_FILE"]).expanduser()
    INSTALL_SQL_DIR = (
        Path(config["MUSICA_SQL_DIR"]).expanduser() / "install"
    )
# End config read

def connect_rw() -> sqlite3.Connection:
    if not DB_FILE.parent.is_dir():
        raise SystemExit(f"ERROR: Missing directory: {DB_FILE.parent} (installer/layout issue)")
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def connect_ro() -> sqlite3.Connection:
    if not DB_FILE.exists():
        raise SystemExit(f"ERROR: DB file not found: {DB_FILE}")
    uri = f"file:{DB_FILE.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def _exists(conn: sqlite3.Connection, obj_type: str, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type=? AND name=?",
        (obj_type, name),
    ).fetchone()
    return row is not None


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM musica_meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO musica_meta(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


# def load_install_sql(conn: sqlite3.Connection) -> None:
#     """
#     Execute all *.sql files in ~/Musica/sql/install in sorted filename order.
#     This is the canonical load step for the SQLite app schema.
#     """
#     if not INSTALL_SQL_DIR.is_dir():
#         raise SystemExit(f"ERROR: install SQL dir not found: {INSTALL_SQL_DIR}")
# 
#     sql_files = sorted(INSTALL_SQL_DIR.glob("*.sql"))
#     if not sql_files:
#         raise SystemExit(f"ERROR: no .sql files found in: {INSTALL_SQL_DIR}")
# 
#     for p in sql_files:
#         sql_text = p.read_text(encoding="utf-8")
#         try:
#             conn.executescript(sql_text)
#         except sqlite3.Error as e:
#             raise SystemExit(f"ERROR executing {p.name}: {e}")
# 
#     conn.commit()

def load_install_sql(conn: sqlite3.Connection) -> None:
    if not INSTALL_SQL_DIR.is_dir():
        raise SystemExit(f"ERROR: install SQL dir not found: {INSTALL_SQL_DIR}")

    sql_files = sorted(INSTALL_SQL_DIR.glob("*.sql"))
    if not sql_files:
        raise SystemExit(f"ERROR: no .sql files found in: {INSTALL_SQL_DIR}")

    # Load non-views first, views last (simple deterministic rule)
    non_views = [p for p in sql_files if not p.name.lower().startswith("v_")]
    views = [p for p in sql_files if p.name.lower().startswith("v_")]
    ordered = non_views + views

    for p in ordered:
        sql_text = p.read_text(encoding="utf-8")
        try:
            conn.executescript(sql_text)
        except sqlite3.Error as e:
            raise SystemExit(f"ERROR executing {p.name}: {e}")

    conn.commit()

def provision_schema_baseline(conn: sqlite3.Connection) -> None:
    """
    Bootstrap provisioning objects (owned by this tool).
    Keep this small and stable.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS musica_meta (
          key   TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS musica_users (
          user_id    INTEGER PRIMARY KEY,
          username   TEXT NOT NULL UNIQUE,
          role       TEXT NOT NULL DEFAULT 'owner',
          created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
          is_active  INTEGER NOT NULL DEFAULT 1
        );

        CREATE VIEW IF NOT EXISTS v_musica_users AS
        SELECT username, role, is_active, created_at
        FROM musica_users;

        CREATE TRIGGER IF NOT EXISTS trg_musica_users_username_nonempty
        BEFORE INSERT ON musica_users
        FOR EACH ROW
        WHEN NEW.username IS NULL OR length(trim(NEW.username)) = 0
        BEGIN
          SELECT RAISE(ABORT, 'username cannot be empty');
        END;
        """
    )
    conn.commit()


def provision_user_and_role(conn: sqlite3.Connection) -> None:
    """
    SQLite analogue of MariaDB user/grant: record current OS user + role metadata.
    """
    username = getpass.getuser()
    conn.execute("INSERT OR IGNORE INTO musica_users(username, role) VALUES(?, 'owner')", (username,))
    conn.execute("UPDATE musica_users SET role='owner' WHERE username=?", (username,))
    conn.commit()


def provision(conn: sqlite3.Connection) -> None:
    # 1) bootstrap schema
    provision_schema_baseline(conn)

    # 2) user + role metadata
    provision_user_and_role(conn)

    # 3) load real app schema from sql/install
    load_install_sql(conn)

    # 4) stamp meta
    set_meta(conn, "schema_version", str(SCHEMA_VERSION))
    set_meta(conn, "provisioned_by", getpass.getuser())
    conn.commit()


def check(conn: sqlite3.Connection) -> int:
    # Integrity
    row = conn.execute("PRAGMA integrity_check;").fetchone()
    result = row[0] if row else None
    if result != "ok":
        print("ERROR: PRAGMA integrity_check failed:", result)
        return 2
    print("OK: integrity_check = ok")

    missing = False

    # Bootstrap objects
    for t in REQUIRED_TABLES:
        if not _exists(conn, "table", t):
            print("ERROR: missing table:", t)
            missing = True
    for v in REQUIRED_VIEWS:
        if not _exists(conn, "view", v):
            print("ERROR: missing view:", v)
            missing = True
    for tr in REQUIRED_TRIGGERS:
        if not _exists(conn, "trigger", tr):
            print("ERROR: missing trigger:", tr)
            missing = True

    # Meta
    sv = get_meta(conn, "schema_version") if _exists(conn, "table", "musica_meta") else None
    print("schema_version:", sv if sv is not None else "(missing)")

    # User
    username = getpass.getuser()
    urow = None
    try:
        urow = conn.execute(
            "SELECT username, role, is_active FROM musica_users WHERE username=?",
            (username,),
        ).fetchone()
    except Exception:
        urow = None

    if not urow:
        print(f"ERROR: user not provisioned in musica_users for current OS user: {username}")
        missing = True
    else:
        if urow["role"] != "owner":
            print(f"ERROR: user role is '{urow['role']}', expected 'owner'")
            missing = True
        if int(urow["is_active"]) != 1:
            print(f"ERROR: user is not active (is_active={urow['is_active']})")
            missing = True
        print(f"OK: user provisioned: {urow['username']} (role={urow['role']})")

    # Install schema present?
    for t in REQUIRED_INSTALL_TABLES:
        if not _exists(conn, "table", t):
            print("ERROR: required install table missing:", t)
            missing = True

    for t in OPTIONAL_INSTALL_TABLES:
        if not _exists(conn, "table", t):
            print("WARNING: optional install table missing:", t)

    for v in OPTIONAL_INSTALL_VIEWS:
        if not _exists(conn, "view", v):
            print("WARNING: optional install view missing:", v)

    return 3 if missing else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Provision Musica SQLite DB (bootstrap + install schema)")
    ap.add_argument("--check", action="store_true", help="Check DB/schema/user only (no changes).")
    args = ap.parse_args()

    # Print/Display primary config data
    print("Musica SQLite Provisioning")
    print("--------------------------")

    load_config()

    print("Config file:", MUSICA_CONFIG_FILE)
    print("Base dir:", MUSICA_BASE_DIR)
    print("DB file:", DB_FILE)
    print("install SQL dir:", INSTALL_SQL_DIR)

    if args.check:
        conn = connect_ro()
        try:
            rc = check(conn)
        finally:
            conn.close()
        sys.exit(rc)

    conn = connect_rw()
    try:
        provision(conn)
    finally:
        conn.close()

    print("OK: Provisioning complete.")


if __name__ == "__main__":
    main()
