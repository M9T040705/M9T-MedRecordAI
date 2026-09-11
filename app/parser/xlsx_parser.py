"""XLSX 解析器：openpyxl 读取所有 Sheet，渲染为 '字段: 值' 文本。

病案首页的 Excel 表格版（字段/值两列）经此转换后可直接喂给抽取器。
"""
from __future__ import annotations

from pathlib import Path

from .base import BaseParser, ParsedDocument, register


@register
class XlsxParser(BaseParser):
    extensions = ["xlsx", "xlsm", "xls"]

    def parse(self, path: Path) -> ParsedDocument:
        from openpyxl import load_workbook

        wb = load_workbook(str(path), data_only=True)
        parts, tables = [], []
        for ws in wb.worksheets:
            rows = []
            for row in ws.iter_rows(values_only=True):
                cells = ["" if c is None else str(c).strip() for c in row]
                if any(cells):
                    rows.append(cells)
            tables.extend([rows])
            for row in rows:
                parts.append(" | ".join(c for c in row if c))
        return ParsedDocument(doc_name=path.name, format="xlsx",
                              text="\n".join(parts), tables=tables)
