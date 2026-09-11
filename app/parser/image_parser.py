"""图片 OCR 解析器：PaddleOCR 封装 + 扫描件版式还原（键值行聚类）。

- OCR_MODE=auto：检测到 paddleocr 则使用真实 OCR；否则抛 OCRError 提示安装；
- OCR_MODE=mock ：演示模式，返回空文本并标注 scanned=True（供流程演示不中断）；
- OCR_MODE=off  ：跳过图片解析。

版式还原：对 OCR 结果按行 y 坐标聚类，把「字段：值」形式的行还原成键值文本，
供病案首页字段抽取使用（对应简历"OCR 版式还原与表格识别"）。
"""
from __future__ import annotations

from pathlib import Path

from ..config import settings
from .base import BaseParser, ParsedDocument, ParseError, register


class OCRError(ParseError):
    pass


def _ocr_image(pil_image) -> list:
    """返回 [(text, (x0,y0,x1,y1)), ...]。"""
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    result = ocr.ocr(pil_image, cls=True)
    lines = []
    for page in (result if isinstance(result, list) else [result]):
        if not page:
            continue
        for item in page:
            box, (text, score) = item[0], item[1]
            lines.append((text, (box[0][0], box[0][1], box[2][0], box[2][1])))
    return lines


def restore_kv_lines(lines: list, y_tol: int = 12) -> str:
    """版式还原：按行 y 坐标聚类 → 行内按 x 排序 → '键: 值' 拼接。"""
    if not lines:
        return ""
    rows: list[list] = []
    for text, (x0, y0, x1, y1) in sorted(lines, key=lambda t: (t[1][1], t[1][0])):
        placed = False
        for row in rows:
            if abs(row[0] - y0) <= y_tol:
                row[1].append((x0, text))
                placed = True
                break
        if not placed:
            rows.append([y0, [(x0, text)]])
    out = []
    for _, cells in sorted(rows, key=lambda r: r[0]):
        cells.sort(key=lambda c: c[0])
        out.append(" ".join(c[1] for c in cells))
    return "\n".join(out)


@register
class ImageParser(BaseParser):
    extensions = ["png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp"]

    def parse(self, path: Path) -> ParsedDocument:
        from PIL import Image

        img = Image.open(str(path)).convert("RGB")
        mode = settings.ocr_mode.lower()
        if mode == "off":
            return ParsedDocument(doc_name=path.name, format=path.suffix.lower().lstrip("."),
                                  text="", scanned=True, image_count=1)
        try:
            lines = _ocr_image(img)
        except ImportError:
            if mode == "mock":
                return ParsedDocument(doc_name=path.name, format=path.suffix.lower().lstrip("."),
                                      text="", scanned=True, image_count=1,
                                      layout={"ocr": "mock（未安装 PaddleOCR）"})
            raise OCRError(
                "未安装 PaddleOCR。请执行：pip install -r requirements-ocr.txt "
                "（建议 Python 3.11 环境），或将 OCR_MODE 设为 mock/off 跳过图片解析。"
            )
        text = restore_kv_lines(lines)
        return ParsedDocument(doc_name=path.name, format=path.suffix.lower().lstrip("."),
                              text=text, scanned=True, image_count=1,
                              layout={"ocr_lines": len(lines)})
