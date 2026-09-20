#!/usr/bin/env python3
"""
musica_db_add_recording_sqlite.py — Interactive single-record insert (SQLite)

Rules:
- Always prompt: artist, title, year, genre, format
- Prompt composer/orchestra/conductor ONLY when genre == 'Symphonic'
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILE = Path.home() / "Musica" / "musica.db"

GENRES = ["Jazz", "Rock", "Country", "Classical", "Symphonic", "Soundtrack"]
FORMATS = ["LP", "CD", "Cass", "RtR", "78", "4T", "8T"]
REC_MODES = ["M", "S", "B"]
YN = ["Y", "N"]


def prompt_required(label: str) -> str:
    while True:
        val = input(f"{label}: ").strip()
        if val:
            return val
        print("Value required.")


def prompt_int(label: str, min_val: int | None = None) -> int:
    while True:
        val = input(f"{label}: ").strip()
        try:
            num = int(val)
            if min_val is not None and num < min_val:
                print(f"Must be >= {min_val}.")
                continue
            return num
        except ValueError:
            print("Invalid number.")


def prompt_choice(label: str, choices: list[str]) -> str:
    while True:
        print(f"{label} ({'/'.join(choices)}): ", end="")
        val = input().strip()
        if val in choices:
            return val
        print("Invalid choice.")

def prompt_choice_default(label: str, choices: list[str], default: str | None = None) -> str | None:
    """
    Prompt for a choice; hitting Enter returns the default (which may be None).
    """
    choices_str = "/".join(choices)
    d = f" [{default}]" if default else ""
    while True:
        val = input(f"{label} ({choices_str}){d}: ").strip()
        if not val:
            return default
        if val in choices:
            return val
        print("Invalid choice.")

def prompt_optional(label: str) -> str | None:
    val = input(f"{label} (optional): ").strip()
    return val if val else None


def yn_prompt(label: str) -> bool:
    return input(f"{label} (y/N): ").strip().lower() == "y"


def main() -> None:
    if not DB_FILE.exists():
        raise SystemExit(f"ERROR: DB not found: {DB_FILE}")

    print("Add New Recording")
    print("-----------------")

    artist = prompt_required("Artist")
    title = prompt_required("Title")
    year = prompt_int("Year", 1900)

    # genre determines whether we ask classical fields
    genre = prompt_choice("Genre", GENRES)

    composer = orchestra = conductor = None
    if genre == "Symphonic":
        composer = prompt_optional("Composer")
        orchestra = prompt_optional("Orchestra")
        conductor = prompt_optional("Conductor")

    fmt = prompt_choice("Format", FORMATS)

    label = prompt_optional("Label")
    catalog = prompt_optional("Catalog Number")

    recording_mode = prompt_choice_default("Recording Mode", REC_MODES, default="S")

    reissue = prompt_choice("Reissue", YN) if yn_prompt("Is this a reissue?") else None
    dbx_encoded = "Y" if yn_prompt("DBX encoded?") else None

    print("\nConfirm Insert")
    print("--------------")
    print(f"Artist: {artist}")
    print(f"Title : {title}")
    print(f"Year  : {year}")
    print(f"Genre : {genre}")
    if genre == "Symphonic":
        print(f"Composer  : {composer or '-'}")
        print(f"Orchestra : {orchestra or '-'}")
        print(f"Conductor : {conductor or '-'}")
    print(f"Format: {fmt}")
    print(f"Label : {label or '-'}")
    print(f"Catalog#: {catalog or '-'}")
    print(f"Mode  : {recording_mode or '-'}")
    print(f"Reissue: {reissue or '-'}")
    print(f"DBX   : {dbx_encoded or '-'}")

    if input("Proceed? (y/N): ").strip().lower() != "y":
        print("Cancelled.")
        return

    sql = """
    INSERT INTO recordings (
        artist, title, year,
        composer, orchestra, conductor,
        genre, format,
        label, catalog_number,
        recording_mode, reissue, dbx_encoded
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        cur = conn.cursor()
        cur.execute(sql, (
            artist, title, year,
            composer, orchestra, conductor,
            genre, fmt,
            label, catalog,
            recording_mode, reissue, dbx_encoded
        ))
        conn.commit()
        print("OK: Recording inserted. id:", cur.lastrowid)
    except sqlite3.IntegrityError as e:
        raise SystemExit(f"ERROR: insert failed (integrity): {e}")
    except sqlite3.OperationalError as e:
        raise SystemExit(f"ERROR: insert failed (operational): {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

