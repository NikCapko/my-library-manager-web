from flask import Blueprint, redirect, request, url_for

from ..models import toggle_favorite

bp = Blueprint("favorites", __name__)


@bp.route("/toggle_fav/<int:book_id>")
def toggle_fav(book_id):
    toggle_favorite(book_id)

    if request.args.get("from") == "book":
        return redirect(url_for("book.view_book", book_id=book_id))

    return redirect(
        url_for(
            "index.index",
            q=request.args.get("q") or None,
            author=request.args.get("author") or None,
            favorite=request.args.get("favorite") or None,
            tag=request.args.getlist("tag") or None,
        )
    )
