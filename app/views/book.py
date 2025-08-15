import json
import os

from flask import Blueprint, abort, redirect, render_template, request, url_for

from ..models import get_book, update_book
from ..rendering import render_book_content

bp = Blueprint("book", __name__)

ALLOWED_LANGS = {"ru", "en", "en-ru"}


from flask import redirect, url_for  # уже импортированы


@bp.route("/book/<int:book_id>")
def view_book(book_id):
    book = get_book(book_id)
    if not book or not book.get("bnf_path"):
        abort(404)

    ver = request.args.get("ver")
    if book["lang"] == "en-ru" and ver is None:
        return redirect(url_for("book.view_book", book_id=book_id, ver="ru"))

    toc, content, parallel = render_book_content(book, ver)
    # определяем режим для <article>
    if ver == "stacked":
        mode = "stacked"
    elif parallel:
        mode = "parallel"
    else:
        mode = "markdown"

    return render_template(
        "book.html",
        book=book,
        content=content,
        toc=toc,
        parallel=parallel,
        mode=mode,
        has_toc=bool(toc),
        ver=ver,
    )


@bp.route("/edit/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    book = get_book(book_id)
    if not book or not book.get("bnf_path"):
        abort(404)

    if request.method == "POST":
        title = request.form["title"].strip()
        orig_name = request.form.get("orig_name", "").strip()
        author = request.form["author"].strip()
        description = request.form["description"].strip()
        lang = request.form["lang"].strip()
        if lang not in ALLOWED_LANGS:
            abort(400)
        tags = [t.strip().lower() for t in request.form["tags"].split(",") if t.strip()]

        fields = {
            "title": title,
            "orig_name": orig_name,
            "author": author,
            "description": description,
            "lang": lang,
        }
        try:
            update_book(book_id, fields, tags)
        except Exception as e:
            return f"<p>Ошибка при обновлении БД: {e}</p>", 500

        try:
            bnf_path = book["bnf_path"]
            data = {}
            if os.path.exists(bnf_path):
                with open(bnf_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data.update(fields)
            data["tags"] = tags
            with open(bnf_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            return f"<p>Ошибка при обновлении BNF: {e}</p>", 500

        return redirect(url_for("book.view_book", book_id=book_id))

    return render_template("edit.html", book=book, tags=", ".join(book["tags"]))
