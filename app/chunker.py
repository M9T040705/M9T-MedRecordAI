"""语义分片器：标题/段落感知，按 token 预算合并并保留重叠。

- 用于医疗合同、医保政策、诊疗规范等长文档；
- 病案首页文本较短，通常整体为一个 Chunk（不切碎，保证字段抽取完整）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import List

from .parser.base import ParsedDocument


@dataclass
class Chunk:
    index: int
    doc_name: str
    section: str
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


class SemanticChunker:
    def __init__(self, budget: int = 500, overlap: int = 50):
        self.budget = budget
        self.overlap = overlap

    def _split_paragraphs(self, text: str) -> List[str]:
        # 按标题/段落切分，保留标题行归属
        parts = []
        for block in re.split(r"\n\s*\n", text):
            block = block.strip()
            if block:
                parts.append(block)
        return parts

    def chunk(self, doc: ParsedDocument) -> List[Chunk]:
        paragraphs = self._split_paragraphs(doc.text)
        if len(doc.text) <= self.budget:
            return [Chunk(0, doc.doc_name, "全文", doc.text)]
        chunks, cur, cur_len = [], [], 0
        for i, para in enumerate(paragraphs):
            if cur_len + len(para) > self.budget and cur:
                chunks.append(Chunk(len(chunks), doc.doc_name, f"段落{len(chunks) + 1}", "\n".join(cur)))
                tail = self._tail(cur, self.overlap)
                cur, cur_len = tail, sum(len(p) for p in tail)
            cur.append(para)
            cur_len += len(para)
        if cur:
            chunks.append(Chunk(len(chunks), doc.doc_name, f"段落{len(chunks) + 1}", "\n".join(cur)))
        return chunks

    @staticmethod
    def _tail(paras: List[str], chars: int) -> List[str]:
        out, n = [], 0
        for p in reversed(paras):
            out.insert(0, p)
            n += len(p)
            if n >= chars:
                break
        return out


def chunk_document(doc: ParsedDocument) -> List[Chunk]:
    return SemanticChunker().chunk(doc)
