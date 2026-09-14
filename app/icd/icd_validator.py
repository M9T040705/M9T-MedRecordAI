"""ICD-10 编码校验器：格式校验 + 字典匹配 + 近邻纠错建议。

- 格式：ICD-10 为 字母+两位数字+可选小数（1-2 位），如 I10、E11.9、J18.901；
- 字典：icd_sample.json 收录高频诊断编码（演示用，生产应接权威 ICD 字典库）；
- 纠错：未命中时按前缀给出最接近的候选，辅助编码员快速修正（对应"ICD 编码校验逻辑"）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

FORMAT_RE = re.compile(r"^[A-Za-z]\d{2}(?:\.\d{1,2})?$")


def _load_dict() -> dict:
    path = Path(__file__).parent / "icd_sample.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _query_db(code: str) -> Optional[dict]:
    """优先从数据库 ICD 编码库查询。"""
    try:
        from ..admin_db import get_icd_by_code
        item = get_icd_by_code(code)
        if item:
            return {"code": item["code"], "name": item["name"]}
    except Exception:
        pass
    return None


def validate_icd(code: str) -> dict:
    code = (code or "").strip().upper()
    if not code:
        return {"code": "", "valid_format": False, "in_dictionary": False,
                "name": "", "suggestion": "编码为空", "matched": False}
    if not FORMAT_RE.match(code):
        return {"code": code, "valid_format": False, "in_dictionary": False,
                "name": "", "suggestion": "格式非法：应为字母+2位数字+可选小数（如 I10、E11.9）",
                "matched": False}
    # 优先查询数据库 ICD 编码库
    db_item = _query_db(code)
    if db_item:
        return {"code": code, "valid_format": True, "in_dictionary": True,
                "name": db_item["name"], "suggestion": "编码有效（来自编码库）", "matched": True}
    # 回退到内置示例字典
    icd_dict = _load_dict()
    if code in icd_dict:
        return {"code": code, "valid_format": True, "in_dictionary": True,
                "name": icd_dict[code], "suggestion": "编码有效", "matched": True}
    # 前缀匹配近邻纠错
    candidates = sorted(icd_dict.keys(), key=lambda c: _prefix_score(code, c), reverse=True)
    best = candidates[0] if candidates else ""
    suggestion = f"未在字典中命中。最接近的编码：{best}（{icd_dict.get(best, '')}）" if best else "字典为空"
    return {"code": code, "valid_format": True, "in_dictionary": False,
            "name": "", "suggestion": suggestion, "matched": False}


def _prefix_score(code: str, candidate: str) -> int:
    """按公共前缀长度打分（含小数点对齐）。"""
    score = 0
    for a, b in zip(code, candidate):
        if a == b:
            score += 1
        else:
            break
    return score
