"""解析器基类与注册表：统一 ParsedDocument 数据结构 + 按扩展名路由。

设计目标（对应简历"适配 7 类文档格式"）：
pdf / docx / xlsx / pptx / 图片(png,jpg,jpeg,bmp,tif) / txt,md / html
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


class ParseError(Exception):
    pass


@dataclass
class ParsedDocument:
    doc_name: str
    format: str
    text: str
    tables: List[List[List[str]]] = field(default_factory=list)   # [ [行[...单元格]] ]
    image_count: int = 0
    scanned: bool = False
    layout: dict = field(default_factory=dict)

    def table_text(self) -> str:
        """把表格渲染成 '键: 值' 风格文本，便于后续抽取。"""
        lines = []
        for table in self.tables:
            for row in table:
                cells = [c.strip() for c in row if c and c.strip()]
                if len(cells) == 2 and cells[0] and cells[1]:
                    lines.append(f"{cells[0]}: {cells[1]}")
                elif cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)


class BaseParser:
    extensions: List[str] = []

    def parse(self, path: Path) -> ParsedDocument:
        raise NotImplementedError


_REGISTRY: List[BaseParser] = []


def register(parser_cls: type) -> type:
    _REGISTRY.append(parser_cls())
    return parser_cls


def get_parser(path: Path) -> Optional[BaseParser]:
    ext = path.suffix.lower().lstrip(".")
    for p in _REGISTRY:
        if ext in p.extensions:
            return p
    return None


def parse_document(path: str | Path) -> ParsedDocument:
    """工厂入口：按扩展名路由解析，未知格式抛 ParseError。"""
    path = Path(path)
    parser = get_parser(path)
    if parser is None:
        raise ParseError(f"不支持的文件格式：{path.suffix}（支持 pdf/docx/xlsx/pptx/png/jpg/jpeg/bmp/tif/txt/md/html）")
    try:
        doc = parser.parse(path)
    except Exception as e:
        raise ParseError(f"{path.suffix} 解析失败：{e}") from e
    doc.doc_name = path.name
    return doc


# 导入子模块完成注册（放在 parse_document 之后避免循环）
from . import docx_parser, image_parser, pdf_parser, pptx_parser, text_parser, xlsx_parser  # noqa: E402,F401
