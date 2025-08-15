"""Подключение к SQLite, коллации, контекстный менеджер, инициализация схемы."""
import sqlite3
from contextlib import contextmanager

from .config import DB_FILE

SCHEMA_VERSION = 3

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    orig_name   TEXT,
    author      TEXT,
    description TEXT,
    lang        TEXT,
    bnf_path    TEXT UNIQUE,
    favorite    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS book_tags (
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (book_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_books_title  ON books(title  COLLATE UNI_NOCASE);
CREATE INDEX IF NOT EXISTS idx_books_author ON books(author COLLATE UNI_NOCASE);
CREATE INDEX IF NOT EXISTS idx_books_fav    ON books(favorite) WHERE favorite = 1;
CREATE INDEX IF NOT EXISTS idx_book_tags_b  ON book_tags(book_id);
CREATE INDEX IF NOT EXISTS idx_book_tags_t  ON book_tags(tag_id);
"""

SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS scan_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL DEFAULT 'running',  -- running|ok|error|cancelled
    total       INTEGER NOT NULL DEFAULT 0,
    count       INTEGER NOT NULL DEFAULT 0,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_scan_runs_started
    ON scan_runs(started_at DESC);
"""

SCHEMA_V3 = """
-- FTS5-таблица: content='' — «внешняя» (хранит только индекс, не данные)
CREATE VIRTUAL TABLE IF NOT EXISTS books_fts USING fts5(
    title,
    orig_name,
    author,
    description,
    content='books',
    content_rowid='id',
    tokenize="unicode61 remove_diacritics 2"
);

-- Наполняем индекс из существующих строк
INSERT INTO books_fts(rowid, title, orig_name, author, description)
SELECT id, title, orig_name, author, description FROM books
WHERE id NOT IN (SELECT rowid FROM books_fts);

-- Синхронизация через триггеры
CREATE TRIGGER IF NOT EXISTS books_ai AFTER INSERT ON books BEGIN
    INSERT INTO books_fts(rowid, title, orig_name, author, description)
    VALUES (new.id, new.title, new.orig_name, new.author, new.description);
END;

CREATE TRIGGER IF NOT EXISTS books_ad AFTER DELETE ON books BEGIN
    INSERT INTO books_fts(books_fts, rowid, title, orig_name, author, description)
    VALUES ('delete', old.id, old.title, old.orig_name, old.author, old.description);
END;

CREATE TRIGGER IF NOT EXISTS books_au AFTER UPDATE ON books BEGIN
    INSERT INTO books_fts(books_fts, rowid, title, orig_name, author, description)
    VALUES ('delete', old.id, old.title, old.orig_name, old.author, old.description);
    INSERT INTO books_fts(rowid, title, orig_name, author, description)
    VALUES (new.id, new.title, new.orig_name, new.author, new.description);
END;
"""

def _register_extensions(conn: sqlite3.Connection) -> None:
    def _cmp(a, b):
        a = "" if a is None else str(a)
        b = "" if b is None else str(b)
        aa, bb = a.casefold(), b.casefold()
        return (aa > bb) - (aa < bb)

    conn.create_collation("UNI_NOCASE", _cmp)
    conn.create_function(
        "UNI_LOWER", 1, lambda s: "" if s is None else str(s).casefold()
    )


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    _register_extensions(conn)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    """Гарантирует commit/rollback и close()."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        v = conn.execute("PRAGMA user_version").fetchone()[0]
        if v < 1:
            conn.executescript(SCHEMA_V1)
            conn.execute("PRAGMA user_version=1")
            v = 1
        if v < 2:
            conn.executescript(SCHEMA_V2)
            conn.execute("PRAGMA user_version=2")
            v = 2
        if v < 3:
            conn.executescript(SCHEMA_V3)
            conn.execute("PRAGMA user_version=3")
