"""TXT / Markdown / HTML 解析器（标准库实现）。"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from .base import BaseParser, ParsedDocument, register


class _HTMLTextExtractor(HTMLParser):
    """把 HTML 转成文本 + 简单表格。"""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.tables: list = []
        self._current_table = None
        self._current_row = None
        self._cell = ""
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "div", "br", "tr", "h1", "h2", "h3", "li"):
            self.parts.append("\n")
        if tag == "table":
            self._current_table = []
        elif tag == "tr" and self._current_table is not None:
            self._current_row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._in_cell = False
            if self._current_row is not None:
                self._current_row.append(self._cell.strip())
        elif tag == "tr" and self._current_row is not None:
            if self._current_table is not None:
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._current_table is not None:
            self.tables.append(self._current_table)
            self._current_table = None

    def handle_data(self, data):
        if self._in_cell:
            self._cell += data
        else:
            self.parts.append(data)


@register
class TextParser(BaseParser):
    extensions = ["txt", "md", "markdown"]

    def parse(self, path: Path) -> ParsedDocument:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return ParsedDocument(doc_name=path.name, format=path.suffix.lower().lstrip("."), text=text)


@register
class HtmlParser(BaseParser):
    extensions = ["html", "htm"]

    def parse(self, path: Path) -> ParsedDocument:
        extractor = _HTMLTextExtractor()
        extractor.feed(path.read_text(encoding="utf-8", errors="ignore"))
        raw = "".join(extractor.parts)
        text = re.sub(r"\n{3,}", "\n\n", raw).strip()
        return ParsedDocument(doc_name=path.name, format="html",
                              text=text, tables=extractor.tables)
