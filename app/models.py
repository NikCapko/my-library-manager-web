"""Доступ к данным: книги, теги, избранное."""

from datetime import datetime, timezone

from .db import db


def _tags_for_book(cur, book_id: int) -> list[str]:
    cur.execute(
        "SELECT name FROM tags "
        "JOIN book_tags ON tags.id = book_tags.tag_id "
        "WHERE book_tags.book_id=?",
        (book_id,),
    )
    return [r[0] for r in cur.fetchall()]


def _row_to_book(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "orig_name": row["orig_name"],
        "description": row["description"],
        "author": row["author"],
        "lang": row["lang"],
        "tags": [],  # заполняется отдельно
        "favorite": row["favorite"],
    }


def _build_query_parts(
    query: str | None,
    tags: list[str] | None,
    author: str | None,
    favorite: bool,
) -> tuple[list[str], list[str], list]:
    """Возвращает (joins, where, params) — общие для count и select."""
    joins: list[str] = []
    where: list[str] = []
    params: list = []

    if author:
        where.append("books.author = ? COLLATE UNI_NOCASE")
        params.append(author)

    if query:
        joins.append(
            "LEFT JOIN book_tags ON books.id = book_tags.book_id "
            "LEFT JOIN tags ON tags.id = book_tags.tag_id"
        )
        where.append(
            "(UNI_LOWER(books.title) LIKE UNI_LOWER(?) "
            "OR UNI_LOWER(books.orig_name) LIKE UNI_LOWER(?) "
            "OR UNI_LOWER(books.author) LIKE UNI_LOWER(?) "
            "OR UNI_LOWER(tags.name) LIKE UNI_LOWER(?) "
            "OR UNI_LOWER(books.description) LIKE UNI_LOWER(?))"
        )
        params += [f"%{query}%"] * 5

    if favorite:
        where.append("books.favorite=1")

    return joins, where, params


def count_books(
    query: str | None = None,
    tags: list[str] | None = None,
    author: str | None = None,
    favorite: bool = False,
) -> int:
    """Общее число книг, подходящих под фильтры (без пагинации)."""
    with db() as conn:
        cur = conn.cursor()

        if tags:
            placeholders = ",".join("?" for _ in tags)
            cur.execute(
                f"""
                SELECT COUNT(*) FROM (
                    SELECT books.id FROM books
                    JOIN book_tags ON books.id = book_tags.book_id
                    JOIN tags ON tags.id = book_tags.tag_id
                    WHERE tags.name IN ({placeholders})
                    GROUP BY books.id
                    HAVING COUNT(DISTINCT tags.name) = ?
                )
                """,
                tuple(tags) + (len(tags),),
            )
            return cur.fetchone()[0]

        joins, where, params = _build_query_parts(query, tags, author, favorite)
        # DISTINCT нужен, потому что query делает JOIN на book_tags
        sql = "SELECT COUNT(DISTINCT books.id) FROM books"
        if joins:
            sql += " " + " ".join(joins)
        if where:
            sql += " WHERE " + " AND ".join(where)
        cur.execute(sql, tuple(params))
        return cur.fetchone()[0]

def get_books(
    query: str | None = None,
    tags: list[str] | None = None,
    author: str | None = None,
    sort: str = "title",
    favorite: bool = False,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[dict], int]:
    """Возвращает (books_на_странице, total).

    Если передан query и sort не задан явно — сортирует по релевантности (bm25).
    """
    if sort not in ("title", "author", "id", "relevance"):
        sort = "title"
    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 500))
    offset = (page - 1) * per_page

    total = count_books(query=query, tags=tags, author=author, favorite=favorite)

    with db() as conn:
        cur = conn.cursor()

        if tags:
            placeholders = ",".join("?" for _ in tags)
            # При наличии query — сначала FTS, потом фильтр по тегам
            if query:
                sql = f"""
                    SELECT books.* FROM books
                    JOIN book_tags ON books.id = book_tags.book_id
                    JOIN tags ON tags.id = book_tags.tag_id
                    WHERE tags.name IN ({placeholders})
                      AND books.id IN (
                          SELECT rowid FROM books_fts WHERE books_fts MATCH ?
                      )
                    GROUP BY books.id
                    HAVING COUNT(DISTINCT tags.name) = ?
                    ORDER BY books.{sort} COLLATE UNI_NOCASE
                    LIMIT ? OFFSET ?
                """
                params = tuple(tags) + (_fts_query(query), len(tags), per_page, offset)
                cur.execute(sql, params)
            else:
                sql = f"""
                    SELECT books.* FROM books
                    JOIN book_tags ON books.id = book_tags.book_id
                    JOIN tags ON tags.id = book_tags.tag_id
                    WHERE tags.name IN ({placeholders})
                    GROUP BY books.id
                    HAVING COUNT(DISTINCT tags.name) = ?
                    ORDER BY books.{sort} COLLATE UNI_NOCASE
                    LIMIT ? OFFSET ?
                """
                cur.execute(sql, tuple(tags) + (len(tags), per_page, offset))
        else:
            joins, where, params = _build_query_parts(query, tags, author, favorite)
            sql = "SELECT DISTINCT books.* FROM books"
            if joins:
                sql += " " + " ".join(joins)
            if where:
                sql += " WHERE " + " AND ".join(where)

            # сортировка
            if query and sort == "relevance":
                # bm25() из FTS: чем меньше — тем релевантнее
                sql = (
                    "SELECT books.* FROM books "
                    "JOIN books_fts ON books_fts.rowid = books.id "
                    + (" " + " ".join(joins) if joins else "")
                    + (" WHERE " + " AND ".join(where) if where else "")
                    + " ORDER BY bm25(books_fts, 5.0, 3.0, 2.0, 1.0) LIMIT ? OFFSET ?"
                )
            else:
                sql += f" ORDER BY books.{sort} COLLATE UNI_NOCASE LIMIT ? OFFSET ?"

            cur.execute(sql, tuple(params) + (per_page, offset))

        rows = cur.fetchall()
        books = [_row_to_book(r) for r in rows]
        for b in books:
            b["tags"] = _tags_for_book(cur, b["id"])

    return books, total

def _fts_query(query: str) -> str:
    """Готовит строку для MATCH. Экранируем, добавляем '*' для префикса."""
    q = (query or "").strip()
    if not q:
        return ""
    # экранируем кавычки, оборачиваем в кавычки — трактуется как фраза
    q = q.replace('"', '""')
    # по последнему слову — префиксный поиск (для автодополнения при вводе)
    parts = q.split()
    if parts:
        parts[-1] = parts[-1] + "*"
    return " ".join(f'"{p}"' if not p.endswith("*") else f'"{p[:-1]}"*' for p in parts)


def _build_query_parts(
    query: str | None,
    tags: list[str] | None,
    author: str | None,
    favorite: bool,
) -> tuple[list[str], list[str], list]:
    """Возвращает (joins, where, params) — общие для count и select.

    query ищется через FTS5 (books_fts MATCH ?).
    """
    joins: list[str] = []
    where: list[str] = []
    params: list = []

    if author:
        where.append("books.author = ? COLLATE UNI_NOCASE")
        params.append(author)

    if query:
        # FTS-подзапрос вместо LIKE
        where.append("books.id IN (SELECT rowid FROM books_fts WHERE books_fts MATCH ?)")
        params.append(_fts_query(query))

    if favorite:
        where.append("books.favorite=1")

    return joins, where, params

def get_book(book_id: int) -> dict | None:
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM books WHERE id=?", (book_id,))
        row = cur.fetchone()
        if not row:
            return None
        book = _row_to_book(row)
        book["bnf_path"] = row["bnf_path"]
        book["tags"] = _tags_for_book(cur, book_id)
        return book


def get_tags_for_book(book_id: int) -> list[str]:
    with db() as conn:
        return _tags_for_book(conn.cursor(), book_id)


def sync_tags(cur, book_id: int, tags: list[str], replace: bool = True) -> None:
    """Единая точка синхронизации тегов."""
    if replace:
        cur.execute("DELETE FROM book_tags WHERE book_id=?", (book_id,))
    for tag in tags:
        tag = (tag or "").strip().lower()
        if not tag:
            continue
        cur.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        cur.execute("SELECT id FROM tags WHERE name=?", (tag,))
        tag_id = cur.fetchone()[0]
        cur.execute(
            "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?, ?)",
            (book_id, tag_id),
        )


def update_book(book_id: int, fields: dict, tags: list[str]) -> None:
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE books SET title=?, orig_name=?, author=?, description=?, lang=? "
            "WHERE id=?",
            (
                fields["title"],
                fields["orig_name"],
                fields["author"],
                fields["description"],
                fields["lang"],
                book_id,
            ),
        )
        sync_tags(cur, book_id, tags, replace=True)


def toggle_favorite(book_id: int) -> int | None:
    """Возвращает новое значение favorite или None, если книги нет."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT favorite FROM books WHERE id=?", (book_id,))
        row = cur.fetchone()
        if not row:
            return None
        new_val = 0 if row[0] else 1
        cur.execute("UPDATE books SET favorite=? WHERE id=?", (new_val, book_id))
        return new_val


def add_or_update_book(
    title: str,
    orig_name: str,
    author: str,
    description: str,
    lang: str | None,
    bnf_path: str,
    tags: list[str],
) -> None:
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM books WHERE UNI_LOWER(title)=UNI_LOWER(?) "
            "AND UNI_LOWER(author)=UNI_LOWER(?)",
            (title, author),
        )
        row = cur.fetchone()
        if row:
            book_id = row[0]
            cur.execute(
                "UPDATE books SET title=?, orig_name=?, author=?, description=?, "
                "lang=?, bnf_path=? WHERE id=?",
                (title, orig_name, author, description, lang, bnf_path, book_id),
            )
            sync_tags(cur, book_id, tags, replace=True)
        else:
            cur.execute(
                "INSERT INTO books (title, orig_name, author, description, lang, bnf_path) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (title, orig_name, author, description, lang, bnf_path),
            )
            book_id = cur.lastrowid
            sync_tags(cur, book_id, tags, replace=False)


def delete_missing_books() -> int:
    """Удаляет книги без файла; чистит осиротевшие теги."""
    import os

    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, bnf_path FROM books")
        rows = cur.fetchall()
        deleted = 0
        for book_id, path in rows:
            if not path or not os.path.exists(path):
                cur.execute("DELETE FROM books WHERE id=?", (book_id,))
                deleted += 1
        cur.execute(
            "DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM book_tags)"
        )
        return deleted


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def scan_run_start(total: int = 0) -> int:
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO scan_runs (started_at, status, total) VALUES (?, 'running', ?)",
            (_now_iso(), total),
        )
        return cur.lastrowid


def scan_run_progress(run_id: int, count: int) -> None:
    with db() as conn:
        conn.execute("UPDATE scan_runs SET count=? WHERE id=?", (count, run_id))


def scan_run_finish(
    run_id: int, status: str, count: int = 0, error: str | None = None
) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE scan_runs SET finished_at=?, status=?, count=?, error=? WHERE id=?",
            (_now_iso(), status, count, error, run_id),
        )


def scan_run_last() -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM scan_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def scan_run_get(run_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM scan_runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None
