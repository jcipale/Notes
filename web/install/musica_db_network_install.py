#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import sys
import platform
import shutil
import sqlite3


# Installation paths are initialized by get_install_path().
MUSICA_BASE_DIR = None
MUSICA_CONFIG_DIR = None
MUSICA_DATA_DIR = None
MUSICA_DB_FILE = None
MUSICA_CONF_PATH = None
MUSICA_CONF_TEMPLATE = None


def get_install_path():
    """Get the Musica installation path from CLI or interactive prompt."""
    if len(sys.argv) > 2:
        print("ERROR: Too many arguments.")
        print(f"Usage: {Path(sys.argv[0]).name} [installation-path]")
        sys.exit(1)

    if len(sys.argv) == 2:
        raw_path = sys.argv[1]
    else:
        default_path = Path.home() / "Musica"
        raw_path = input(
            f"Musica installation directory [{default_path}]: "
        ).strip()
        if not raw_path:
            raw_path = str(default_path)

    base_dir = Path(raw_path).expanduser().resolve()

    global MUSICA_BASE_DIR, MUSICA_CONFIG_DIR, MUSICA_DATA_DIR
    global MUSICA_DB_FILE, MUSICA_CONF_PATH, MUSICA_CONF_TEMPLATE

    MUSICA_BASE_DIR = base_dir
    MUSICA_CONFIG_DIR = base_dir / "config"
    MUSICA_DATA_DIR = base_dir / "data"
    MUSICA_DB_FILE = base_dir / "musica.db"
    MUSICA_CONF_PATH = MUSICA_CONFIG_DIR / "musica.conf"
    MUSICA_CONF_TEMPLATE = MUSICA_CONFIG_DIR / "musica.conf-template"


def refuse_root():
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("ERROR: Do not run this installer as root/sudo.")
        print("Installation target may be local or network storage, but must not be run as root.")
        sys.exit(1)


def detect_os():
    system = platform.system()
    print(f"Detected OS family (raw): {system}")
    print(f"Platform string         : {platform.platform()}")
    return system


def verify_existing_layout():
    print("\nSTEP 2: Verifying existing install layout (no modifications)")
    print("-------------------------------------------------------------")

    required = [
        ("MUSICA_BASE_DIR", MUSICA_BASE_DIR),
        ("MUSICA_CONFIG_DIR", MUSICA_CONFIG_DIR),
        ("MUSICA_DATA_DIR", MUSICA_DATA_DIR),
    ]

    for name, path in required:
        if not path.exists():
            print(f"ERROR: Missing required path: {name} -> {path}")
            print("Installer policy: will not create directories; layout must already exist.")
            sys.exit(1)
        if not path.is_dir():
            print(f"ERROR: Expected directory but found something else: {path}")
            sys.exit(1)
        print(f"OK: {name} = {path}")


def generate_config_if_missing():
    print("\nSTEP 3: Verifying musica.conf (generate only if missing)")
    print("-------------------------------------------------------------")

    if MUSICA_CONF_PATH.exists():
        print(f"OK: musica.conf exists: {MUSICA_CONF_PATH}")
        return

    # Only generate if missing, and ONLY from the installed template.
    if not MUSICA_CONF_TEMPLATE.is_file():
        print(f"ERROR: musica.conf missing and template not found: {MUSICA_CONF_TEMPLATE}")
        print("Safe-upgrade policy: will not fall back to tarball templates.")
        sys.exit(1)

    template_text = MUSICA_CONF_TEMPLATE.read_text(encoding="utf-8")
    rendered = template_text.replace("__MUSICA_BASE_DIR__", str(MUSICA_BASE_DIR))

    # Write new config
    MUSICA_CONF_PATH.write_text(rendered, encoding="utf-8")
    print(f"Created musica.conf from installed template: {MUSICA_CONF_PATH}")


def validate_config_syntax_only():
    """
    Syntax-only validation: KEY=VALUE with comments/blanks allowed.
    Does NOT expand ${VAR}, and does NOT mkdir anything.
    """
    print("\nSTEP 4: Validating musica.conf syntax (no expansions, no side effects)")
    print("-------------------------------------------------------------")

    if not MUSICA_CONF_PATH.is_file():
        print(f"ERROR: Missing config file: {MUSICA_CONF_PATH}")
        sys.exit(1)

    with MUSICA_CONF_PATH.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue

            # strip inline comment markers (simple)
            for c in ("#", ";"):
                if c in line:
                    line = line.split(c, 1)[0].rstrip()
            if not line:
                continue

            if "=" not in line:
                print(f"ERROR: Invalid config syntax at line {lineno}")
                print(f">>> {raw.rstrip()}")
                sys.exit(1)

    print("OK: musica.conf syntax looks valid.")


def ensure_sqlite_db_file():
    print("\nSTEP 5: Ensuring SQLite DB exists (only artifact we create)")
    print("-------------------------------------------------------------")

    try:
        conn = sqlite3.connect(str(MUSICA_DB_FILE))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("SELECT 1;")
        conn.close()
    except Exception as e:
        print(f"ERROR: Failed to create/open SQLite DB file: {MUSICA_DB_FILE}")
        print(f"Reason: {e}")
        sys.exit(1)

    print(f"OK: SQLite DB openable: {MUSICA_DB_FILE}")


def final_summary():
    print("\n-------------------------------------------------------------")
    print("Musica install verification complete (SQLite).")
    print(f"Base dir : {MUSICA_BASE_DIR}")
    print(f"Config   : {MUSICA_CONF_PATH}")
    print(f"DB file  : {MUSICA_DB_FILE}")
    # print("NOTE: Existing config/data/logs were not modified.")
    print("NOTE: Existing config/data were not modified.")
    print("-------------------------------------------------------------")


def main():
    print("Musica Installer – Verify/Finalize (SQLite)")
    refuse_root()

    print("\nSTEP 1: OS detection")
    print("-----------------------------------------------------")
    detect_os()

    get_install_path()
    print(f"Selected installation directory: {MUSICA_BASE_DIR}")

    verify_existing_layout()
    generate_config_if_missing()
    validate_config_syntax_only()
    ensure_sqlite_db_file()
    final_summary()


if __name__ == "__main__":
    main()

