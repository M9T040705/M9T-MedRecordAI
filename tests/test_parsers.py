"""解析器单测：覆盖 7 类格式（txt/md/pdf/docx/xlsx + 未知格式报错）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))

from app.parser.base import ParseError, parse_document  # noqa: E402


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    from gen_samples import generate_samples
    d = tmp_path_factory.mktemp("samples")
    generate_samples(d)
    return d


def test_txt_parser(samples):
    doc = parse_document(samples / "sample01.txt")
    assert doc.format == "txt"
    assert "张伟" in doc.text and "I10" in doc.text


def test_md_parser(samples):
    doc = parse_document(samples / "sample02.md")
    assert "王芳" in doc.text


def test_pdf_parser(samples):
    doc = parse_document(samples / "sample03.pdf")
    assert doc.format == "pdf"
    assert "刘强" in doc.text
    assert doc.scanned is False


def test_docx_parser(samples):
    doc = parse_document(samples / "sample04.docx")
    assert "陈静" in doc.text
    assert len(doc.tables) >= 1
    assert "姓名" in doc.table_text()


def test_xlsx_parser(samples):
    doc = parse_document(samples / "sample05.xlsx")
    assert "李娜" in doc.text
    assert "性别" in doc.table_text()


def test_unknown_format_raises(samples):
    f = samples / "sample01.unknownext"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_document(f)
