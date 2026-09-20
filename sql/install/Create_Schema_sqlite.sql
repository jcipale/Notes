-- Create_Schema_sqlite.sql — recordings
-- SQLite 3.x

-- recordings table
CREATE TABLE IF NOT EXISTS recordings (
    id INTEGER PRIMARY KEY,                        -- rowid-backed autoincrement behavior
    artist TEXT NOT NULL,
    title  TEXT NOT NULL,

    year INTEGER NOT NULL
        CHECK (year >= 1900),

    composer TEXT,
    orchestra TEXT,
    conductor TEXT,

    genre  TEXT NOT NULL
        CHECK (genre IN ('Jazz','Rock','Country','Classical','Symphonic','Soundtrack')),

    format TEXT NOT NULL
        CHECK (format IN ('LP','CD','Cass','RtR','78','4T','8T')),

    label TEXT,
    catalog_number TEXT,

    recording_mode TEXT
        CHECK (recording_mode IN ('M','S','B')),

    reissue TEXT
        CHECK (reissue IN ('Y','N')),

    dbx_encoded TEXT
        CHECK (dbx_encoded IN ('Y'))
);

-- index
CREATE INDEX IF NOT EXISTS idx_recordings_artist_title_year
ON recordings (artist, title, year);

-- triggers (SQLite supports DROP TRIGGER IF EXISTS)
DROP TRIGGER IF EXISTS trg_recordings_year_ins;
CREATE TRIGGER trg_recordings_year_ins
BEFORE INSERT ON recordings
FOR EACH ROW
WHEN NEW.year > (CAST(strftime('%Y','now') AS INTEGER) + 1)
BEGIN
  SELECT RAISE(ABORT, 'Invalid year: exceeds allowed range');
END;

DROP TRIGGER IF EXISTS trg_recordings_year_upd;
CREATE TRIGGER trg_recordings_year_upd
BEFORE UPDATE ON recordings
FOR EACH ROW
WHEN NEW.year > (CAST(strftime('%Y','now') AS INTEGER) + 1)
BEGIN
  SELECT RAISE(ABORT, 'Invalid year: exceeds allowed range');
END;

