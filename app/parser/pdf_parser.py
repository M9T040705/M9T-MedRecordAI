"""PDF 解析器：PyMuPDF 文本 + 表格提取 + 扫描件检测。

- 数字版 PDF：直接抽取文本与表格（find_tables）；
- 扫描版 PDF（文本密度过低）：标记 scanned，交由 OCR 管线处理。
"""
from __future__ import annotations

from pathlib import Path

from .base import BaseParser, ParsedDocument, register

TEXT_DENSITY_THRESHOLD = 20   # 每页少于该字符数判定为扫描件


@register
class PdfParser(BaseParser):
    extensions = ["pdf"]

    def parse(self, path: Path) -> ParsedDocument:
        import pymupdf

        pages_text, tables, image_count = [], [], 0
        scanned = False
        page_count = 0
        with pymupdf.open(str(path)) as doc:
            page_count = doc.page_count
            for page in doc:
                text = page.get_text("text", sort=True).strip()
                pages_text.append(text)
                image_count += len(page.get_images(full=True))
                if text:
                    try:
                        for t in page.find_tables().tables:
                            tables.append(t.extract())
                    except Exception:
                        pass
        full_text = "\n\n".join(pages_text)
        if not full_text or len(full_text) < TEXT_DENSITY_THRESHOLD * page_count:
            scanned = True
        return ParsedDocument(
            doc_name=path.name, format="pdf", text=full_text,
            tables=tables, image_count=image_count, scanned=scanned,
            layout={"pages": page_count, "scanned": scanned},
        )
