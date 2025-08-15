"""Сканирование библиотеки и фоновое обновление БД."""

"""Сканирование библиотеки и фоновое обновление БД."""
import json
import os
import threading

from .models import (
    add_or_update_book,
    delete_missing_books,
    scan_run_finish,
    scan_run_progress,
    scan_run_start,
)

_scan_lock = threading.Lock()
_scan_status = {"running": False, "count": 0, "error": None}


def status() -> dict:
    return dict(_scan_status)


def start_scan(folder: str) -> bool:
    """Запускает фоновое сканирование. Возвращает False, если уже идёт."""
    if not _scan_lock.acquire(blocking=False):
        return False
    try:
        if _scan_status["running"]:
            return False
        _scan_status.update(running=True, count=0, error=None)
    finally:
        _scan_lock.release()

    threading.Thread(target=_worker, args=(folder,), daemon=True).start()
    return True


def _worker(folder: str) -> None:
    count = 0
    try:
        for root, _, files in os.walk(folder):
            for file in files:
                if not file.endswith(".bnf"):
                    continue
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    add_or_update_book(
                        data.get("title", ""),
                        data.get("orig_name", ""),
                        data.get("author", ""),
                        data.get("description", ""),
                        lang=data.get("lang"),
                        bnf_path=path,
                        tags=data.get("tags", []),
                    )
                    count += 1
                    _scan_status["count"] = count
                except Exception as e:
                    print(f"Ошибка {file}: {e}")
        delete_missing_books()
    except Exception as e:
        _scan_status["error"] = str(e)
    finally:
        _scan_status["running"] = False


_scan_lock = threading.Lock()
_scan_status = {"running": False, "count": 0, "total": 0, "error": None, "run_id": None}


def status() -> dict:
    return dict(_scan_status)


def start_scan(folder: str) -> bool:
    """Запускает фоновое сканирование. False — если уже идёт."""
    if not _scan_lock.acquire(blocking=False):
        return False
    try:
        if _scan_status["running"]:
            return False
        # предварительно посчитаем .bnf — для прогресса
        total = _count_bnf(folder)
        run_id = scan_run_start(total=total)
        _scan_status.update(
            running=True,
            count=0,
            total=total,
            error=None,
            run_id=run_id,
        )
    finally:
        _scan_lock.release()

    threading.Thread(target=_worker, args=(folder, run_id), daemon=True).start()
    return True


def _count_bnf(folder: str) -> int:
    n = 0
    for _, _, files in os.walk(folder):
        n += sum(1 for f in files if f.endswith(".bnf"))
    return n


def _worker(folder: str, run_id: int) -> None:
    count = 0
    error: str | None = None
    try:
        for root, _, files in os.walk(folder):
            for file in files:
                if not file.endswith(".bnf"):
                    continue
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    add_or_update_book(
                        data.get("title", ""),
                        data.get("orig_name", ""),
                        data.get("author", ""),
                        data.get("description", ""),
                        lang=data.get("lang"),
                        bnf_path=path,
                        tags=data.get("tags", []),
                    )
                    count += 1
                    _scan_status["count"] = count
                    scan_run_progress(run_id, count)
                except Exception as e:
                    print(f"Ошибка {file}: {e}")
        delete_missing_books()
        final_status = "ok"
    except Exception as e:
        error = str(e)
        _scan_status["error"] = error
        final_status = "error"
    finally:
        _scan_status.update(
            running=False,
            count=count,
            error=error,
            run_id=None,
        )
        scan_run_finish(run_id, final_status, count=count, error=error)
