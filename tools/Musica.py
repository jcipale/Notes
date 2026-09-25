#!/usr/bin/env python3
"""
musica.py — final exporter (v4.21)

Usage:
  - Place your user JSON (not the template) in the same folder as this script.
  - JSON must contain at least:
      { "username": "<discogs_user>", "token": "<discogs_token>" }
  - Run:
      ./musica.py

Output:
  - Semicolon-separated CSV named: Musica_Export_mm.dd.yyyy.csv

Notes:
  - Artist rules: Option 3 (band names preserved; only obvious Discogs reversals fixed)
  - Composer: CE3 (only explicit composer metadata is used)
  - Multi-artist: MA1 (join with '/'; persons normalized as Last, First)
  - Featuring: ignored (F1)
"""

import os
import sys
import json
import requests
from time import sleep
from pathlib import Path
from datetime import datetime
import re


# tools/Musica.py
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

EXPORT_DIR = PROJECT_ROOT / "data" / "imports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

date_str = datetime.now().strftime("%m.%d.%Y")

out_name = EXPORT_DIR / f"Musica_Import_{date_str}.csv"

# -------------------------
# Progress bar
# -------------------------
def progress_bar(current, total, width=40):
    if total is None or total <= 0:
        return
    ratio = float(current) / float(total)
    filled = int(width * ratio)
    bar = "=" * filled + "-" * (width - filled)
    sys.stdout.write(f"\r[{bar}] {ratio * 100:5.1f}%")
    sys.stdout.flush()
    if current == total:
        print()

# -------------------------
# Constants / Keywords
# -------------------------
ORCHESTRA_KEYWORDS = ["orchestra", "symphony", "philharmonic", "philharmonia", "ensemble", "pops", "chorus", "choir"]
BAND_KEYWORDS = ["band", "trio", "quartet", "quintet", "ensemble", "project", "collective", "combo", "orchestra"]
THE_PREFIX = re.compile(r'^\s*the\s+', flags=re.I)

# -------------------------
# Heuristics
# -------------------------
def move_leading_the(name):
    if not name:
        return ""
    s = name.strip()
    if "," in s:
        return s
    m = THE_PREFIX.match(s)
    if m:
        remainder = s[m.end():].strip()
        return f"{remainder}, The"
    return s

def looks_like_person(name):
    """
    Conservative person detection:
      - If contains comma and RHS has space -> likely 'Last, First Middle'
      - If two tokens both capitalized (First Last) and no orchestra keyword -> likely person
      - Prevent treating obvious band keywords as person
    """
    if not name:
        return False
    s = name.strip()
    if "," in s:
        left, right = [p.strip() for p in s.split(",", 1)]
        if " " in right:
            return True
        if re.search(r'\b(jr|sr|ii|iii|iv)\b', right, flags=re.I):
            return True
    tokens = s.split()
    if len(tokens) == 2 and tokens[0] and tokens[1]:
        if tokens[0][0].isupper() and tokens[1][0].isupper():
            low = s.lower()
            if not any(k in low for k in ORCHESTRA_KEYWORDS + BAND_KEYWORDS):
                return True
    return False

def obvious_reversal_fix(name):
    """
    Fix only obvious reversal cases where Discogs has 'X, Y' but this is not a person.
    Rules:
      - If name contains a comma and does NOT look like a person, flip once: 'A, B' -> 'B A'
      - Also handle simple 'Steamroller, Mannheim' -> 'Mannheim Steamroller'
      - Then apply 'The' move to end
    Conservative: do NOT flip if looks_like_person(name) == True.
    """
    if not name:
        return ""
    s = name.strip()
    # remove numeric suffixes like (2)
    s = re.sub(r'\s*\(\d+\)\s*$', '', s).strip()
    if "," not in s:
        return move_leading_the(s)
    # if looks like person, keep as-is
    if looks_like_person(s):
        return move_leading_the(s)
    # safe flip
    left, right = [p.strip() for p in s.split(",", 1)]
    flipped = f"{right} {left}"
    return move_leading_the(flipped)

def normalize_person(name):
    """
    Normalize a person to Last, First... if possible.
    If already in Last, First keep as-is.
    If given as First Last, convert.
    Apply 'The' rule only for non-persons.
    """
    if not name:
        return ""
    s = name.strip()
    s = re.sub(r'\s*\(\d+\)\s*$', '', s).strip()
    if "," in s:
        # already last, first — keep
        return s
    tokens = s.split()
    if len(tokens) == 1:
        return s
    return f"{tokens[-1]}, {' '.join(tokens[:-1])}"

# -------------------------
# Field normalizers
# -------------------------
def normalize_artist_field(name):
    """
    Main Artist normalizer per Option 3:
      - If entry is orchestra-like, return empty (we won't keep orchestras in Artist)
      - If looks like person -> normalize_person (Last, First)
      - Otherwise -> apply obvious_reversal_fix (flip only if clearly not person)
      - Do NOT decompose band names into people
    """
    if not name:
        return ""
    s = name.strip()
    low = s.lower()
    # if looks orchestra-like, do not include in Artist
    if any(k in low for k in ORCHESTRA_KEYWORDS):
        return ""
    # if looks like person (conservative)
    if looks_like_person(s):
        return normalize_person(s)
    # else flip only in obvious reversed non-person cases
    return obvious_reversal_fix(s)

def normalize_title(t):
    if not t:
        return ""
    s = t.strip()
    # convert middot or semicolon lists to slash-separated multi-work title
    if "·" in s:
        parts = [p.strip() for p in s.split("·") if p.strip()]
        if len(parts) > 1:
            return "/".join(parts)
    if ";" in s:
        parts = [p.strip() for p in s.split(";") if p.strip()]
        if len(parts) > 1:
            return "/".join(parts)
    if ":" in s and len(s.split(":",1)[0].split()) <= 3:
        # "Composer: Work" -> take RHS
        return s.split(":",1)[1].strip()
    return move_leading_the(s)

def normalize_format(fmt_list):
    if not fmt_list:
        return ""
    text = " ".join(fmt_list).lower()
    if "Vinyl" in text: return "LP"
    if "LP" in text: return "LP"
    if "78 RPM" in text in text: return "78"
    if "45 RPM" in text in text: return "45"
    if "Cylinder" in text : return "Cyl"
    if "CD" in text and "cd-rom" not in text: return "CD"
    if "Cassette" in text: return "Cass"
    if "Reel-To-Reel" in text: return "RTR"
    if "8-Track Cartridge" in text or "8 track" in text: return "8T"
    if "4-Track Cartridge" in text or "8 track" in text: return "4T"
    return " ".join(fmt_list)

def detect_recording_mode(formats):
    if not formats:
        return ""
    parts = []
    for f in formats:
        if isinstance(f, dict):
            parts.append(f.get("name","") or "")
            parts.append(" ".join(f.get("descriptions",[]) or []))
            if "text" in f:
                parts.append(str(f.get("text","")))
        else:
            parts.append(str(f))
    joined = " ".join(parts).lower()
    mono = "mono" in joined
    stereo = "stereo" in joined
    if mono and stereo:
        return ""
    if mono:
        return "M"
    if stereo:
        return "S"
    return ""

def detect_dbx(formats, notes):
    parts = []
    for f in formats:
        if isinstance(f, dict):
            parts.append(f.get("name","") or "")
            parts.append(" ".join(f.get("descriptions",[]) or []))
            if "text" in f:
                parts.append(str(f.get("text","")))
        else:
            parts.append(str(f))
    combined = " ".join(parts) + " " + (notes or "")
    return "Y" if "dbx" in combined.lower() else ""

def detect_reissue(formats, notes):
    parts = []
    for f in formats:
        if isinstance(f, dict):
            parts.append(" ".join(f.get("descriptions",[]) or []))
            parts.append(f.get("name","") or "")
        else:
            parts.append(str(f))
    combined = " ".join(parts) + " " + (notes or "")
    low = combined.lower()
    if "reissue" in low or "repress" in low or "remaster" in low or "remastered" in low:
        return "Y"
    return ""

def normalize_genre(genres):
    if not genres:
        return ""
    norms = [g.lower().strip() for g in genres if g]
    for g in norms:
        if any(k in g for k in ("jazz","funk","soul","blues","r&b","fusion")):
            return "jazz"
    for g in norms:
        if any(k in g for k in ("stage & screen","soundtrack","score","musical","stage")):
            return "soundtrack"
    for g in norms:
        if any(k in g for k in ("classical","symphony","opera","choral","baroque","romantic")):
            return "classical"
    for g in norms:
        if any(k in g for k in ("country","country rock","bluegrass")):
            return "country"
    for g in norms:
        if any(k in g for k in ("folk","world","folk, world")):
            return "rock"
    for g in norms:
        if any(k in g for k in ("rock","pop","metal","punk","alternative","indie")):
            return "rock"
    for g in norms:
        if any(k in g for k in ("electronic","ambient","house","techno","trance","synth")):
            return "jazz"
    for g in norms:
        if any(k in g for k in ("hip hop","rap","trap")):
            return ""
    return ""

# -------------------------
# Extractors
# -------------------------
def extract_artists_field(info):
    arts = info.get("artists", []) or []
    names = []
    # If a band name appears in artists[], prefer the band alone (per rule)
    # Detect presence of any clear-band token in artists[]
    has_band = False
    for a in arts:
        nm = a.get("name","").strip() if isinstance(a, dict) else str(a).strip()
        if nm and any(k in nm.lower() for k in BAND_KEYWORDS + ORCHESTRA_KEYWORDS):
            has_band = True
            break
    # If a band is present in artists[], we will return the first band-like artist as Artist.
    if has_band:
        # prefer first band-like entry
        for a in arts:
            nm = a.get("name","").strip() if isinstance(a, dict) else str(a).strip()
            if not nm:
                continue
            if any(k in nm.lower() for k in BAND_KEYWORDS + ORCHESTRA_KEYWORDS):
                # but if orchestra-like, we will treat it as orchestra later (so skip)
                if any(k in nm.lower() for k in ORCHESTRA_KEYWORDS):
                    continue
                return obvious_reversal_fix(nm)
        # fallback: if no band-like (non-orchestra) found, continue to normal behavior below

    # Normal case: collect non-orchestra artist entries, normalize each and join with '/'
    for a in arts:
        nm = a.get("name","").strip() if isinstance(a, dict) else str(a).strip()
        if not nm:
            continue
        if any(k in nm.lower() for k in ORCHESTRA_KEYWORDS):
            # skip orchestra-like entries for artist
            continue
        normalized = normalize_artist_field(nm)
        if normalized:
            names.append(normalized)
    return "/".join(names)

def extract_composer(info):
    # CE3: only explicit composer roles
    for a in (info.get("extraartists",[]) or []):
        if not a:
            continue
        name = a.get("name","").strip() if isinstance(a, dict) else str(a).strip()
        role = (a.get("role","") or "").lower() if isinstance(a, dict) else ""
        if any(k in role for k in ("composer","composed","written")):
            # explicit composer — return normalized person if person-like, else best-effort normalized
            return normalize_person(name) if looks_like_person(name) else obvious_reversal_fix(name)
    # tracklist extras
    for tr in (info.get("tracklist",[]) or []):
        if isinstance(tr, dict):
            for a in (tr.get("extraartists",[]) or []):
                if not a:
                    continue
                name = a.get("name","").strip() if isinstance(a, dict) else str(a).strip()
                role = (a.get("role","") or "").lower() if isinstance(a, dict) else ""
                if any(k in role for k in ("composer","composed","written")):
                    return normalize_person(name) if looks_like_person(name) else obvious_reversal_fix(name)
    return ""  # CE3 — do not infer

def extract_orchestra_conductor(info):
    orchestra = ""
    conductor = ""
    for a in (info.get("extraartists",[]) or []):
        if not a:
            continue
        name = a.get("name","").strip() if isinstance(a, dict) else str(a).strip()
        role = (a.get("role","") or "").lower() if isinstance(a, dict) else ""
        ln = name.lower()
        if not orchestra and (any(k in role for k in ORCHESTRA_KEYWORDS) or any(k in ln for k in ORCHESTRA_KEYWORDS)):
            # normalize to "Name Orchestra" if reversed, etc.
            orchestra = obvious_reversal_fix(name)
            # ensure suffix if needed: e.g., "London Symphony" -> "London Symphony Orchestra"
            if not any(orchestra.lower().endswith(k) for k in ORCHESTRA_KEYWORDS):
                orchestra = orchestra + " Orchestra"
        if not conductor and any(k in role for k in ("conductor","conducted","directed","leader")):
            conductor = normalize_person(name) if looks_like_person(name) else obvious_reversal_fix(name)
    # scan tracklist extras too
    for tr in (info.get("tracklist",[]) or []):
        if isinstance(tr, dict):
            for a in (tr.get("extraartists",[]) or []):
                if not a:
                    continue
                name = a.get("name","").strip() if isinstance(a, dict) else str(a).strip()
                role = (a.get("role","") or "").lower() if isinstance(a, dict) else ""
                ln = name.lower()
                if not orchestra and (any(k in role for k in ORCHESTRA_KEYWORDS) or any(k in ln for k in ORCHESTRA_KEYWORDS)):
                    orchestra = obvious_reversal_fix(name)
                    if not any(orchestra.lower().endswith(k) for k in ORCHESTRA_KEYWORDS):
                        orchestra = orchestra + " Orchestra"
                if not conductor and any(k in role for k in ("conductor","conducted","directed","leader")):
                    conductor = normalize_person(name) if looks_like_person(name) else obvious_reversal_fix(name)
    # fallback: if no orchestra yet but artists[] contains an orchestra-only entry, use it
    if not orchestra:
        for a in (info.get("artists",[]) or []):
            nm = a.get("name","").strip() if isinstance(a, dict) else str(a).strip()
            if nm and any(k in nm.lower() for k in ORCHESTRA_KEYWORDS):
                orchestra = obvious_reversal_fix(nm)
                if not any(orchestra.lower().endswith(k) for k in ORCHESTRA_KEYWORDS):
                    orchestra = orchestra + " Orchestra"
                break
    return orchestra or "", conductor or ""

# -------------------------
# Config loader and Discogs fetch
# -------------------------
def load_config():
    json_files = [f for f in os.listdir(".") if f.lower().endswith(".json") and "tmpl" not in f.lower()]
    if not json_files:
        print("ERROR: No JSON config found in current directory. Place your <user>.json here (not the template).")
        sys.exit(1)
    if len(json_files) == 1:
        cfgfile = json_files[0]
    else:
        print("Available JSON config files:")
        for i, fn in enumerate(json_files, 1):
            print(f"  {i}) {fn}")
        choice = input("Select config file [1]: ").strip()
        try:
            idx = int(choice) - 1 if choice and choice.isdigit() else 0
            if idx < 0 or idx >= len(json_files):
                idx = 0
        except Exception:
            idx = 0
        cfgfile = json_files[idx]
    with open(cfgfile, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    print(f"Using config: {cfgfile}")
    return cfg

def fetch_discogs_collection(username, token):
    base = f"https://api.discogs.com/users/{username}/collection/folders/0/releases"
    headers = {"User-Agent": "Musica_Exporter/4.21"}
    params = {"token": token, "per_page": 100, "page": 1}
    releases = []
    total = None
    print("\nFetching Discogs collection...")
    while True:
        r = requests.get(base, headers=headers, params=params)
        if r.status_code != 200:
            print(f"\nERROR: HTTP {r.status_code} when fetching page {params['page']}")
            break
        data = r.json()
        if total is None:
            total = data.get("pagination",{}).get("items",0)
        releases.extend(data.get("releases",[]))
        progress_bar(len(releases), total or 0)
        next_url = data.get("pagination",{}).get("urls",{}).get("next")
        if not next_url:
            break
        params["page"] += 1
        sleep(0.15)
    print(f"\nDownload complete: {len(releases)} items.\n")
    return releases

# -------------------------
# Main
# -------------------------
def main():
    cfg = load_config()
    username = cfg.get("username") or cfg.get("user") or ""
    token = cfg.get("token") or cfg.get("access_token") or ""
    if not username or not token:
        print("ERROR: Config must include 'username' and 'token'.")
        sys.exit(1)

    releases = fetch_discogs_collection(username, token)
    #date_str = datetime.now().strftime("%m.%d.%Y")
    #out_name = f"Musica_Export_{date_str}.csv"

    headers = ["Artist","Title","Year","Composer","Orchestra","Conductor","Genre","Format","Label","Catalog_Number","Recording_Mode","Reissue","DBX_Encoded"]

    with open(out_name, "w", encoding="utf-8") as out:
        out.write(";".join(headers) + "\n")
        total = len(releases)
        for i, rel in enumerate(releases, start=1):
            info = rel.get("basic_information", {}) or {}

            # Artist(s) per Option 3 (conservative)
            artist_field = extract_artists_field(info)

            # Title
            title = normalize_title(info.get("title","") or "")

            # Year
            year = str(info.get("year") or "")

            # Composer (CE3: only explicit)
            composer = extract_composer(info)

            # Orchestra and conductor (strict)
            orchestra, conductor = extract_orchestra_conductor(info)

            # Genre
            genre = normalize_genre(info.get("genres",[]) or [])

            # Apply C1: for classical/soundtrack, if conductor present use conductor as Artist
            artist_for_row = artist_field
            if genre in ("classical","soundtrack") and conductor:
                artist_for_row = conductor

            # Format
            formats = info.get("formats", []) or []
            fmt_names = []
            for f in formats:
                if isinstance(f, dict):
                    if f.get("name"):
                        fmt_names.append(f.get("name"))
                else:
                    fmt_names.append(str(f))
            fmt = normalize_format(fmt_names)

            # Label / Catalog
            labels = info.get("labels",[]) or []
            if labels and isinstance(labels[0], dict):
                label = labels[0].get("name","") or ""
                catalog = labels[0].get("catno","") or ""
            else:
                label = labels[0] if labels else ""
                catalog = ""

            # Recording mode / reissue / dbx
            recording_mode = detect_recording_mode(formats)
            reissue = detect_reissue(formats, info.get("notes","") or "")
            dbx = detect_dbx(formats, info.get("notes","") or "")

            row = [
                artist_for_row or "", title or "", year or "", composer or "", orchestra or "", conductor or "",
                genre or "", fmt or "", label or "", catalog or "", recording_mode or "", reissue or "", dbx or ""
            ]
            safe_row = [str(x).replace("\n"," ").replace("\r"," ") for x in row]
            out.write(";".join(safe_row) + "\n")

            if i % 20 == 0 or i == total:
                progress_bar(i, total)

    print(f"\nExport finished: {out_name}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")

