"""Рендер markdown, параллельный режим, расширения markdown."""

from __future__ import annotations

import html
import os
import re

import markdown
from markdown import Extension
from markdown.blockprocessors import HashHeaderProcessor
from markdown.extensions.toc import TocExtension


class StrictHeaderProcessor(HashHeaderProcessor):
    """Заголовки только с пробелом после #."""

    RE = re.compile(r"(?:^|\n)(?P<level>#{1,6})\s+(?P<header>.*?)\s*#*(\n|$)")


class StrictHeadersExtension(Extension):
    def extendMarkdown(self, md):
        md.parser.blockprocessors.register(
            StrictHeaderProcessor(md.parser), "strict_hashheader", 70
        )
        md.parser.blockprocessors.deregister("hashheader")


def _make_md() -> markdown.Markdown:
    return markdown.Markdown(
        extensions=[StrictHeadersExtension(), TocExtension(), "nl2br"]
    )


def render_markdown_file(path: str) -> tuple[str, str]:
    """Возвращает (toc_html, body_html)."""
    if not os.path.exists(path):
        return "", f"[Файл {path} не найден]"
    with open(path, "r", encoding="utf-8") as f:
        md_text = f.read()
    md = _make_md()
    body = md.convert(md_text)
    return md.toc or "", body


def render_parallel(en_file: str, ru_file: str) -> tuple[str, str, bool]:
    """Построчный параллельный режим: таблица 2 колонки по 100vw."""
    if not (os.path.exists(en_file) and os.path.exists(ru_file)):
        return "", "[Файлы EN и RU не найдены]", True

    with open(en_file, "r", encoding="utf-8") as f:
        en_lines = [line.rstrip("\n") for line in f]
    with open(ru_file, "r", encoding="utf-8") as f:
        ru_lines = [line.rstrip("\n") for line in f]

    n = max(len(en_lines), len(ru_lines))
    en_lines += [""] * (n - len(en_lines))
    ru_lines += [""] * (n - len(ru_lines))

    parts = ['<div class="parallel-scroll"><table class="parallel">']
    parts.append("<thead><tr><th>EN</th><th>RU</th></tr></thead>")
    parts.append("<tbody>")
    for en_line, ru_line in zip(en_lines, ru_lines):
        parts.append(
            "<tr>"
            f'<td class="parallel-cell parallel-en">{html.escape(en_line) or "&nbsp;"}</td>'
            f'<td class="parallel-cell parallel-ru">{html.escape(ru_line) or "&nbsp;"}</td>'
            "</tr>"
        )
    parts.append("</tbody></table></div>")

    return "", "".join(parts), True


def render_stacked(en_file: str, ru_file: str) -> tuple[str, str, bool]:
    """EN построчно; RU свёрнут под каждой строкой, раскрывается по клику.
    Возвращает (toc, html, parallel=True) — parallel=True, чтобы book.html
    знал, что это не обычный markdown-body.
    """
    if not (os.path.exists(en_file) and os.path.exists(ru_file)):
        return "", "[Файлы EN и RU не найдены]", True

    with open(en_file, "r", encoding="utf-8") as f:
        en_lines = [line.rstrip("\n") for line in f]
    with open(ru_file, "r", encoding="utf-8") as f:
        ru_lines = [line.rstrip("\n") for line in f]

    n = max(len(en_lines), len(ru_lines))
    en_lines += [""] * (n - len(en_lines))
    ru_lines += [""] * (n - len(ru_lines))

    parts = [
        '<div class="stacked-toolbar">',
        '<button type="button" id="stackedToggleAll" data-state="collapsed">'
        "Показать все RU</button>",
        "</div>",
        '<div class="stacked" id="stacked">',
    ]
    for idx, (en_line, ru_line) in enumerate(zip(en_lines, ru_lines)):
        en_html = html.escape(en_line) or "&nbsp;"
        ru_html = html.escape(ru_line) or "&nbsp;"
        # пустые пары — не рисуем кнопку, только EN, чтобы не плодить мусор
        if not ru_line.strip():
            parts.append(
                f'<div class="stacked-pair stacked-pair-empty">'
                f'<div class="stacked-en">{en_html}</div>'
                f"</div>"
            )
        else:
            parts.append(
                f'<div class="stacked-pair">'
                f'<div class="stacked-en">{en_html}'
                f'<button type="button" class="stacked-toggle" '
                f'data-target="ru-{idx}" aria-expanded="false" '
                f'title="Показать перевод">RU</button>'
                f"</div>"
                f'<div class="stacked-ru" id="ru-{idx}" hidden>{ru_html}</div>'
                f"</div>"
            )
    parts.append("</div>")

    return "", "".join(parts), True


def render_book_content(book: dict, ver: str | None) -> tuple[str, str, bool]:
    folder = os.path.dirname(book["bnf_path"])
    base = os.path.splitext(os.path.basename(book["bnf_path"]))[0]
    lang = book["lang"]

    if lang in ("ru", "en"):
        toc, body = render_markdown_file(os.path.join(folder, f"{base}.md"))
        return toc, body, False

    if lang == "en-ru":
        if ver == "ru":
            toc, body = render_markdown_file(os.path.join(folder, f"{base}.ru.md"))
            return toc, body, False
        if ver == "en":
            toc, body = render_markdown_file(os.path.join(folder, f"{base}.en.md"))
            return toc, body, False
        if ver == "stacked":
            return render_stacked(
                os.path.join(folder, f"{base}.en.md"),
                os.path.join(folder, f"{base}.ru.md"),
            )
        return render_parallel(
            os.path.join(folder, f"{base}.en.md"),
            os.path.join(folder, f"{base}.ru.md"),
        )

    return "", f"[Неизвестный язык: {lang}]", False
