from __future__ import annotations

from datetime import datetime

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from ..config import LIBRARY_PATH
from ..models import scan_run_get, scan_run_last
from ..scanning import start_scan, status

bp = Blueprint("scan", __name__)


def _human_dt(iso: str | None) -> str | None:
    """ISO 8601 UTC -> читаемая локальная строка."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
        return dt.astimezone().strftime("%d.%m.%Y %H:%M:%S")
    except ValueError:
        return iso


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} с"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m} мин {s} с"
    h, m = divmod(m, 60)
    return f"{h} ч {m} мин"


def _decorate(run: dict | None) -> dict | None:
    """Добавляет человеко-читаемые поля к записи scan_run."""
    if not run:
        return None
    out = dict(run)
    out["started_human"] = _human_dt(run["started_at"])
    out["finished_human"] = _human_dt(run["finished_at"])
    if run.get("started_at") and run.get("finished_at"):
        try:
            s = datetime.fromisoformat(run["started_at"])
            f = datetime.fromisoformat(run["finished_at"])
            out["duration_human"] = _fmt_duration((f - s).total_seconds())
        except ValueError:
            pass
    return out


@bp.route("/update_books")
def update_books():
    """Страница обновления: статус последнего запуска + кнопка."""
    last = _decorate(scan_run_last())
    current = status()
    # если сейчас что-то выполняется — покажем это
    running_run = None
    if current["running"] and current.get("run_id"):
        running_run = _decorate(scan_run_get(current["run_id"]))
    return render_template(
        "update.html",
        last=last,
        running=current["running"],
        running_run=running_run,
        current=current,
    )


@bp.route("/update_books/start", methods=["POST"])
def update_books_start():
    """Запускает сканирование. Возвращает JSON для AJAX или redirect."""
    ok = start_scan(LIBRARY_PATH)
    wants_json = (
        request.accept_mimetypes.best == "application/json"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )
    if wants_json:
        return jsonify({"started": ok, **status()}), (200 if ok else 409)
    return redirect(url_for("scan.update_books"))


@bp.route("/update_status")
def update_status():
    current = status()
    # добавим инфо о последнем завершённом, если сейчас ничего не идёт
    if not current["running"]:
        current["last"] = _decorate(scan_run_last())
    return jsonify(current)
