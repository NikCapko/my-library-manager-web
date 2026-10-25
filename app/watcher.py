"""Наблюдение за папкой библиотеки (опционально)."""
import queue
import threading

from .config import MYLIB_LIBRARY_PATH

try:
    from watchdog.observers import Observer
    from library_watcher import LibraryWatcher
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

event_queue: "queue.Queue | None" = None


def start_watcher(folder: str = MYLIB_LIBRARY_PATH) -> bool:
    global event_queue
    if not _AVAILABLE:
        print("watchdog/library_watcher недоступны — наблюдение не запущено")
        return False
    if event_queue is not None:
        return True
    event_queue = queue.Queue()
    handler = LibraryWatcher(event_queue)
    observer = Observer()
    observer.schedule(handler, folder, recursive=True)
    observer.daemon = True
    observer.start()
    print(f"Наблюдение за {folder} запущено")
    threading.Thread(target=observer.join, daemon=True).start()
    return True
