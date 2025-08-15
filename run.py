"""Точка входа. Dev: python run.py. Prod: waitress-serve --call app:create_app."""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5050"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    # В проде используйте waitress:
    #   waitress-serve --host=0.0.0.0 --port=5050 --call app:create_app
    app.run(host=host, port=port, debug=debug)
