from flask import Blueprint, render_template, request

from ..models import _fts_query, get_books

bp = Blueprint("index", __name__)

PER_PAGE = 50


@bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    author = request.args.get("author", "").strip()
    sort = request.args.get("sort", "title")
    favorite = request.args.get("favorite", "") == "1"
    tags = request.args.getlist("tag")

    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    page = max(1, page)

    books, total = get_books(
        query=q or None,
        tags=tags or None,
        author=author or None,
        sort=sort,
        favorite=favorite,
        page=page,
        per_page=PER_PAGE,
    )

    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    # если запросили страницу за пределами — покажем последнюю
    if page > pages and total > 0:
        page = pages
        books, total = get_books(
            query=q or None,
            tags=tags or None,
            author=author or None,
            sort=sort,
            favorite=favorite,
            page=page,
            per_page=PER_PAGE,
        )

    return render_template(
        "index.html",
        books=books,
        query=q,
        tags=tags,
        author=author,
        sort=sort,
        favorite=favorite,
        page=page,
        pages=pages,
        total=total,
        per_page=PER_PAGE,
    )


@bp.route("/suggest")
def suggest():
    from flask import jsonify

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"titles": [], "authors": [], "tags": []})

    from ..models import db

    fts_q = _fts_query(q)  # из models
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT books.title FROM books_fts
            JOIN books ON books.id = books_fts.rowid
            WHERE books_fts MATCH ?
            ORDER BY bm25(books_fts, 5.0, 3.0, 2.0, 1.0)
            LIMIT 8
            """,
            (fts_q,),
        )
        titles = [r[0] for r in cur.fetchall()]

        cur.execute(
            "SELECT DISTINCT author FROM books "
            "WHERE UNI_LOWER(author) LIKE UNI_LOWER(?) LIMIT 5",
            (f"%{q}%",),
        )
        authors = [r[0] for r in cur.fetchall() if r[0]]

        cur.execute(
            "SELECT name FROM tags WHERE UNI_LOWER(name) LIKE UNI_LOWER(?) LIMIT 5",
            (f"%{q}%",),
        )
        tags = [r[0] for r in cur.fetchall()]

    return jsonify({"titles": titles, "authors": authors, "tags": tags})
