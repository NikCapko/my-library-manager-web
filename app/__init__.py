"""Фабрика приложения и регистрация blueprint'ов."""
from flask import Flask

from .config import SECRET_KEY
from .db import init_db


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY

    init_db()

    from .views.index import bp as index_bp
    from .views.book import bp as book_bp
    from .views.favorites import bp as fav_bp
    from .views.scan import bp as scan_bp

    app.register_blueprint(index_bp)
    app.register_blueprint(book_bp)
    app.register_blueprint(fav_bp)
    app.register_blueprint(scan_bp)

    @app.template_global()
    def url_with(keep_page: bool = False, **overrides):
        """Собирает URL index с учётом текущих args.
        По умолчанию page сбрасывается на 1 при смене фильтров,
        если не передан keep_page=True или явный page=.
        """
        from flask import request, url_for

        args = request.args.to_dict(flat=False)
        for key, value in overrides.items():
            if value is None:
                args.pop(key, None)
            elif isinstance(value, (list, tuple)):
                args[key] = [str(v) for v in value] if value else []
            else:
                args[key] = [str(value)]

        # Сброс страницы, если меняются фильтры и page явно не задан
        if not keep_page and "page" not in overrides:
            args.pop("page", None)

        flat = {}
        for k, values in args.items():
            values = [v for v in values if v not in ("", None)]
            if not values:
                continue
            flat[k] = values[0] if len(values) == 1 else values
        return url_for("index.index", **flat)

    return app
